import logging
import threading
import time
from datetime import datetime
from typing import Callable, Dict, Any, List, Optional, Sequence
from pathlib import Path
from backend.src.dataclasses.data import Highlight, Project
from backend.src.infrastructure.youtube_client import ProcessingUnreadableError, YoutubeClient
from backend.src.services.clipper import Clipper
from backend.src.services.description_builder import build_description
from backend.src.services.thumbnailer import Thumbnailer

logger = logging.getLogger(__name__)


class ClipNotRenderedError(Exception):
    """The cut this upload was supposed to publish did not produce a file.

    Not the same as a render that fell over — that arrives as whatever the
    engine raised. This is the render reporting success while leaving the
    highlight with no filename on it, which there is nothing to publish from.
    """


class ClipFileMissingError(Exception):
    """The metadata says this clip was rendered, but the file is not on disk."""


class ClipNotPublishedError(Exception):
    """This clip has no video on YouTube, so nothing can be set on it."""


class UploadInProgressError(Exception):
    """This clip is already being published by another request."""


class Uploader:
    # YouTube goes on processing a video after its last byte has landed, and
    # the end of that processing writes YouTube's own generated thumbnail over
    # whatever was set in the meantime. The set made straight after the upload
    # is accepted — it answers 200 and its response names the picture — and is
    # then thrown away minutes later, which is why the same image attached by
    # hand afterwards stays. So it is set again once YouTube says it has
    # finished, and that set is the one that survives.
    #
    # How often to ask, and for how long. Asking costs 1 unit of quota against
    # the 10,000 a day a default project gets, so a clip that takes five
    # minutes to process is answered in twenty questions rather than watched.
    THUMBNAIL_POLL_SECONDS = 15
    THUMBNAIL_POLL_LIMIT = 80  # 20 minutes, past which the video is not normal

    # Used only when the answer cannot be had — a token authorised before the
    # readonly scope was asked for. Blind waits, in seconds between one attempt
    # and the next, on the chance that one of them lands after processing.
    THUMBNAIL_RETRY_DELAYS = (30, 120, 300)

    def __init__(self, thumbnailer: Optional[Thumbnailer] = None,
                 thumbnail_retry_delays: Optional[Sequence[float]] = None,
                 client_factory: Optional[Callable[[], YoutubeClient]] = None,
                 poll_seconds: Optional[float] = None,
                 poll_limit: Optional[int] = None,
                 clipper: Optional[Clipper] = None):
        self.thumbnails = thumbnailer or Thumbnailer()
        # Held for the same reason the thumbnailer is: publishing a clip means
        # producing the file first, not finding one somebody else left behind.
        self.clipper = clipper or Clipper()
        self.thumbnail_retry_delays = (
            self.THUMBNAIL_RETRY_DELAYS if thumbnail_retry_delays is None
            else tuple(thumbnail_retry_delays)
        )
        self.poll_seconds = self.THUMBNAIL_POLL_SECONDS if poll_seconds is None else poll_seconds
        self.poll_limit = self.THUMBNAIL_POLL_LIMIT if poll_limit is None else poll_limit
        # The re-sets run on their own thread and must not share the handle the
        # uploads are using: a googleapiclient service wraps one httplib2 Http,
        # which two threads cannot be in at once.
        self.client_factory = client_factory or YoutubeClient

    def reset_metadata(self, project: Project) -> None:
        """Clears upload-related artifacts and updates project state."""
        project.set_property("uploads", [])
        project.set_step_status("upload", "pending")

    def start_service(self, project: Project) -> None:
        """Initializes the service."""
        self.reset_metadata(project)
        project.set_step_status("upload", "running")

    def end_service(self, project: Project) -> None:
        """Finalizes the service."""
        project.set_step_status("upload", "completed")

    def clip_path(self, project: Project, highlight: Highlight) -> Path:
        return Path(project.base_directory) / project.project_id / "clips" / highlight.generated_clip_filename

    def open_client(self) -> YoutubeClient:
        """Opens the handle an upload will go through.

        Called before anything is cut, so a missing or expired authorisation is
        reported as itself and at once, rather than after minutes of encoding
        spent on an upload that was never going to happen.
        """
        return self.client_factory()

    def begin_attempt(self, project: Project, index: int) -> None:
        """Clears the last failure, because this attempt is about to replace it."""
        self._set_upload_error(project, index, None)

    def record_failure(self, project: Project, index: int, message: str) -> None:
        """Stores why this attempt produced no video.

        The publish runs in the background, so the response to the click is a
        job key rather than an outcome. This is where the outcome goes.
        """
        logger.warning(f"Upload of clip {index} in {project.project_id} failed: {message}")
        self._set_upload_error(project, index, message)

    def _set_upload_error(self, project: Project, index: int, message: Optional[str]) -> None:
        highlights = project.highlights
        if index >= len(highlights):
            return
        if highlights[index].upload_error == message:
            return
        highlights[index].upload_error = message
        project.set_property("highlights", highlights)

    def _record_upload(self, project: Project, index: int, result: Dict[str, Any]) -> None:
        """Writes the published video back onto the highlight it came from.

        Stored so the clip page can say a clip is already live and link to it —
        publishing is the one action here that cannot be undone from this app,
        and a second click on a button that looks untouched is how it happens
        twice.
        """
        highlights = project.highlights
        if index >= len(highlights):
            return
        highlights[index].youtube_video_id = result.get("video_id")
        highlights[index].youtube_url = result.get("url")
        highlights[index].uploaded_at = datetime.now().isoformat()
        # Whatever the previous attempt failed with is no longer true of this
        # clip, and a live video sitting next to an error message reads as one.
        highlights[index].upload_error = None
        project.set_property("highlights", highlights)

    def upload_one(
        self,
        project: Project,
        index: int,
        client: Optional[YoutubeClient] = None,
    ) -> Dict[str, Any]:
        """Cuts a single clip afresh, publishes it, and returns its id and URL.

        The cut is not conditional on there being no file: the clip the user
        approved is the one drawn from the settings as they stand now — its
        captions, its overlay title, the project's aspect ratio — and a file cut
        before the last of those changes is a different clip. Re-cutting is what
        makes the video on YouTube the video that was on the page.

        Raises IndexError for a position with no highlight, whatever the render
        raised when it could not produce a file, and ClipFileMissingError when
        the file it reported writing is not there.
        """
        # Checked before anything expensive happens, so a position with no
        # highlight is refused rather than rendered.
        if index < 0 or index >= len(project.highlights):
            raise IndexError(f"No highlight at index {index}")

        # Before the render, not after: an authorisation that cannot upload is
        # worth knowing about now rather than at the end of an encode.
        client = client or self.client_factory()

        self.clipper.render_one(project, index)
        # Re-read: the render writes the filename and the timestamp onto the
        # highlight, and the copy taken above predates both.
        highlight = project.highlights[index]

        if not highlight.is_clip_generated or not highlight.generated_clip_filename:
            raise ClipNotRenderedError(
                "The render finished without producing a file for this clip. "
                "The backend log has what ffmpeg reported."
            )

        path = self.clip_path(project, highlight)
        if not path.exists():
            raise ClipFileMissingError(
                f"The file this render reported writing is not there ({path})."
            )

        # The title is the one written for YouTube; the hook is the overlay
        # burned into the frame and only stands in when there is no title.
        title = highlight.video_title_for_youtube_short or highlight.viral_hook_text
        # Built from the template rather than from a single model field, so the
        # link back to the full episode and the user's standing text travel with
        # every upload.
        description = build_description(project, highlight)

        logger.info(f"Uploader uploading clip={highlight.generated_clip_filename} to YouTube")
        logger.info(f"Uploading with title: '{title}'")
        result = client.upload_video(
            file_path=str(path),
            title=title,
            description=description,
        )
        logger.info(
            f"Uploader uploaded clip={highlight.generated_clip_filename}, "
            f"video_id={result.get('video_id')}"
        )
        result["thumbnail_set"] = self._attach_thumbnail(
            project, index, highlight, result.get("video_id"), client
        )
        self._record_upload(project, index, result)
        return result

    def verify_publication(
        self, project: Project, index: int, client: Optional[YoutubeClient] = None
    ) -> Optional[bool]:
        """Whether this clip's published video is still on YouTube.

        Nothing tells this application when a video it published is deleted, so
        the record outlives the video: the clip page goes on offering a dead
        link, and the thumbnail button goes on offering to set a picture on
        nothing. This is the only way to find out, and it is asked lazily —
        when a clip is opened, and before a thumbnail is sent.

        A video that has gone takes its record with it: the id, the url and the
        upload timestamp are cleared, so the clip reads as unpublished
        everywhere and can be published again as though for the first time.

        Returns True if it is there, False if it is gone or was never
        published, and None when the question could not be asked — no read
        scope, no network, a quota refusal. None leaves the record alone: not
        being able to check is not evidence of anything.
        """
        highlight = project.highlights[index]
        if not highlight.youtube_video_id:
            return False

        client = client or self.open_client()
        exists = client.video_exists(highlight.youtube_video_id)
        if exists is None:
            return None
        if exists:
            return True

        logger.info(
            f"Clip {index} of {project.project_id} points at {highlight.youtube_video_id}, "
            "which is no longer on YouTube; clearing the record"
        )
        self._clear_publication(project, index)
        return False

    def _clear_publication(self, project: Project, index: int) -> None:
        """Forgets everything this application knew about a published video."""
        highlights = project.highlights
        highlight = highlights[index]
        highlight.youtube_video_id = None
        highlight.youtube_url = None
        highlight.uploaded_at = None
        highlight.upload_error = None
        project.set_property("highlights", highlights)

    def upload_thumbnail(
        self,
        project: Project,
        index: int,
        client: Optional[YoutubeClient] = None,
    ) -> Dict[str, Any]:
        """Puts the clip's current thumbnail on the video it was published as.

        For a clip whose picture has changed since it went up, and for the ones
        published before the uploader sent the file on disk at all. Nothing is
        re-uploaded: the video keeps its id, its views and its comments, and
        only the still changes.

        Raises IndexError for a position with no highlight, and
        ClipNotPublishedError for a clip that was never uploaded — there is no
        video to put a picture on.
        """
        highlight = project.highlights[index]
        if not highlight.youtube_video_id:
            raise ClipNotPublishedError(
                "This clip has not been published yet, so there is no video to put a "
                "thumbnail on. Upload it first."
            )

        # Checked before anything is sent. A video deleted on YouTube leaves the
        # id behind, and without this the thumbnail was uploaded against it and
        # failed somewhere less legible than here.
        client = client or YoutubeClient()
        if self.verify_publication(project, index, client=client) is False:
            raise ClipNotPublishedError(
                "The video this clip was published as is no longer on YouTube, so "
                "there is nothing to put a thumbnail on. Upload the clip again first."
            )
        # Re-read: verify_publication rewrites the highlights when it clears a
        # record, and this one is about to be used.
        highlight = project.highlights[index]

        logger.info(
            f"Uploader setting the thumbnail of clip {index} on {highlight.youtube_video_id}"
        )
        attached = self._attach_thumbnail(
            project, index, highlight, highlight.youtube_video_id, client
        )
        return {
            "thumbnail_set": attached,
            "video_id": highlight.youtube_video_id,
            "url": highlight.youtube_url,
        }

    def _attach_thumbnail(self, project: Project, index: int, highlight: Highlight,
                          video_id: Optional[str], client: YoutubeClient) -> bool:
        """Sets the clip's thumbnail on the video just published.

        The file in the project's `thumbnails/` directory is what gets sent —
        the picture the user made and can look at. An earlier version rendered
        a fresh one here instead and overwrote that file with it, so the
        picture on YouTube was never the one on disk, and the overwrite hid the
        difference the moment it happened.

        Only a clip with no thumbnail at all is rendered here, because a video
        published without one gets a frame of YouTube's choosing.

        Never fatal. The video is live by the time this runs, so a thumbnail
        that will not render, or will not attach — an unverified channel is the
        usual reason, and nothing about it can be fixed from here — must not be
        reported as a failed upload. It is reported as what it is: published,
        without the picture.
        """
        if not video_id:
            return False

        path = self.thumbnails.path(project, project.highlights[index])
        if path is None or not path.exists():
            try:
                self.thumbnails.generate(project, index)
            except Exception as e:
                logger.warning(f"Uploaded {video_id} but could not make its thumbnail: {e}")
                return False
            path = self.thumbnails.path(project, project.highlights[index])
        if path is None or not path.exists():
            return False
        try:
            response = client.set_thumbnail(video_id, str(path))
        except Exception as e:
            logger.warning(f"Uploaded {video_id} but could not set its thumbnail: {e}")
            return False
        logger.info(f"Set the thumbnail for {video_id} from {path}: {response}")
        self._keep_thumbnail_set(video_id, path)
        return True

    def _keep_thumbnail_set(self, video_id: str, path: Path) -> None:
        """Sets the same thumbnail again once YouTube has finished the video.

        Runs on a daemon thread: the caller is answering an HTTP request, and
        this waits out however long processing takes. Nothing is reported back
        — the video is live either way, and what comes of this is a picture,
        not the upload's outcome.
        """
        if not self.thumbnail_retry_delays and not self.poll_limit:
            return

        def resend():
            try:
                # Its own handle: a googleapiclient service wraps one
                # httplib2.Http, which this thread cannot share with the upload
                # that started it.
                client = self.client_factory()
            except Exception as e:
                logger.warning(f"Could not open YouTube to re-set the thumbnail for {video_id}: {e}")
                return

            finished = self._await_processing(client, video_id)
            if finished is False:
                # Processing failed or the video is gone. There is nothing left
                # to hang a picture on.
                return
            # A single set the moment it is known to be safe; the blind
            # schedule only for a token that could not be asked.
            delays = (0,) if finished else self.thumbnail_retry_delays

            for delay in delays:
                if delay:
                    time.sleep(delay)
                if not path.exists():
                    # The clip was deleted, or the project was cleaned up,
                    # while this was waiting.
                    return
                try:
                    client.set_thumbnail(video_id, str(path))
                    logger.info(f"Set the thumbnail for {video_id} again, after processing"
                                if finished else
                                f"Set the thumbnail for {video_id} again after {delay}s")
                except Exception as e:
                    # Not fatal to the attempts after it: a refusal here is as
                    # often the video not being ready yet as it is the channel
                    # having no custom thumbnails at all.
                    logger.warning(f"Could not set the thumbnail for {video_id} again: {e}")

        threading.Thread(target=resend, name=f"thumbnail-{video_id}", daemon=True).start()

    def _await_processing(self, client: YoutubeClient, video_id: str) -> Optional[bool]:
        """Waits for YouTube to finish with the video.

        True once it has succeeded, False when it failed or the video cannot be
        seen any more, and None when this token cannot be told — which is not a
        failure, only the difference between attaching the thumbnail on an
        answer and attaching it on a guess.
        """
        for attempt in range(self.poll_limit):
            try:
                status = client.processing_status(video_id)
            except ProcessingUnreadableError as e:
                logger.info(f"Falling back to timed thumbnail retries for {video_id}: {e}")
                return None
            except Exception as e:
                logger.warning(f"Could not read the processing state of {video_id}: {e}")
                return None

            if status is None:
                logger.warning(f"YouTube no longer lists {video_id}; leaving its thumbnail alone")
                return False
            if status != "processing":
                logger.info(f"YouTube finished {video_id} after ~{attempt * self.poll_seconds}s: {status}")
                return status == "succeeded"
            time.sleep(self.poll_seconds)

        logger.warning(
            f"{video_id} was still processing after "
            f"{self.poll_limit * self.poll_seconds}s; setting its thumbnail anyway"
        )
        return True

    async def execute(self, project: Project) -> List[Dict[str, Any]]:  # pragma: no cover
        logger.info(f"Uploader executing for project={project.project_id}, highlight_count={len(project.highlights)}")
        self.start_service(project)
        # One client for the whole run: building it is an OAuth refresh, and
        # doing that per clip is both slower and one more thing to fail halfway.
        client = YoutubeClient()

        uploads_list = []
        # Every highlight, cut or not: each one is re-cut on its way up, so this
        # step no longer needs the clipper to have run first — it only needs the
        # source video and the highlights.
        #
        # Indexes, not the highlights themselves: each upload is written back
        # onto its highlight, which reloads the list from disk.
        for index in range(len(project.highlights)):
            try:
                uploads_list.append(self.upload_one(project, index, client=client))
            except Exception as e:
                # One clip that will not cut or will not publish must not
                # abandon the clips after it; the run is still reported as
                # completed with what it did publish, and the clip carries its
                # own reason.
                logger.warning(f"Skipping clip {index} for {project.project_id}: {e}")
                self.record_failure(project, index, str(e) or e.__class__.__name__)

        self.end_service(project)
        logger.info(f"Uploader completed for project={project.project_id}")
        return uploads_list
