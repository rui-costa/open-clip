import logging
import os
from pathlib import Path
import googleapiclient.discovery
import googleapiclient.http
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from typing import Dict, Any, Optional

from backend.src.infrastructure.youtube_auth import stored_scopes

logger = logging.getLogger(__name__)


# Any of these lets `videos.list` be called for the channel's own uploads.
READ_SCOPES = {
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtubepartner",
}


class ProcessingUnreadableError(Exception):
    """This token cannot be told how far along a video's processing is.

    Its own type because it is not a failure of the upload or of the video: it
    is a token authorised before the readonly scope was asked for, and the only
    consequence is that a thumbnail has to be attached on a guess instead of on
    an answer.
    """


class MissingCredentialsError(Exception):
    """No usable YouTube credentials on disk.

    Its own type because it is the one upload failure the user can fix without
    touching the app: connect the channel and try again. Everything else is a
    server or network fault.
    """


class YoutubeClient:
    """
    Manages the YouTube API service handle and the implementation of upload logic.
    """
    def __init__(self, credentials_path: str = "backend/youtube_credentials/youtube_credentials.json"):
        creds = None
        if os.path.exists(credentials_path):
            # The scopes the token was granted, not the ones the app would ask
            # for today: a token from before the readonly scope existed must
            # still upload rather than be refused for what it lacks.
            creds = Credentials.from_authorized_user_file(
                credentials_path, stored_scopes(Path(credentials_path))
            )

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                raise MissingCredentialsError(
                    "No usable YouTube credentials. Authorise a channel so "
                    f"{credentials_path} holds a token that can still be refreshed, then upload again."
                )
        
        self.scopes = list(creds.scopes or [])
        self.service = googleapiclient.discovery.build("youtube", "v3", credentials=creds)

    def can_read_processing(self) -> bool:
        """Whether this token may ask how far along a video's processing is."""
        return bool(READ_SCOPES & set(self.scopes))

    def processing_status(self, video_id: str) -> Optional[str]:
        """How far YouTube has got with a video: what to wait on before the
        thumbnail is attached.

        One of "processing", "succeeded", "failed" or "terminated", or None for
        a video this channel cannot see — deleted, or belonging to someone else.

        Raises ProcessingUnreadableError when the token has no read scope, so
        the caller can fall back to waiting blindly rather than treat a
        permission problem as a video that never finishes.
        """
        if not self.can_read_processing():
            raise ProcessingUnreadableError(
                "This YouTube token was authorised without the readonly scope, so "
                "the processing state of a video cannot be read. Reconnect the "
                "channel in Settings to let thumbnails wait for processing to finish."
            )
        response = self.service.videos().list(
            part="processingDetails", id=video_id
        ).execute()
        items = response.get("items") or []
        if not items:
            return None
        return items[0].get("processingDetails", {}).get("processingStatus")

    def video_exists(self, video_id: str) -> Optional[bool]:
        """Whether this channel can still see the video behind an id.

        False for one that has been deleted on YouTube — the case this
        application cannot otherwise detect, because nothing tells it when a
        video it published stops existing.

        None when the token cannot answer: without the readonly scope the
        question is a permission error rather than a "no", and treating those
        the same would throw away a perfectly good record.
        """
        if not self.can_read_processing():
            return None
        try:
            response = self.service.videos().list(part="id", id=video_id).execute()
        except Exception:
            # A network failure or a quota refusal is not evidence that the
            # video is gone.
            logger.warning(f"Could not check whether {video_id} still exists", exc_info=True)
            return None
        return bool(response.get("items"))

    def upload_video(self, file_path: str, title: str, description: str) -> Dict[str, Any]:
        body = {
            "snippet": {"title": title, "description": description},
            "status": {"privacyStatus": "private"},
        }
        request = self.service.videos().insert(
            part="snippet,status",
            body=body,
            media_body=googleapiclient.http.MediaFileUpload(file_path, chunksize=-1, resumable=True),
        )
        response = None
        while response is None:
            status, response = request.next_chunk()
        video_id = response["id"]
        return {
            "video_id": video_id,
            "url": f"https://youtube.com/watch?v={video_id}",
            # A Short's "Related video" — the chip that sends a viewer to the
            # full episode — cannot be set by this API. `videos.insert` has no
            # field for it, and YouTube exposes it only in Studio, so the URL of
            # the page that does have it travels back with the upload. The link
            # in the description is a separate thing and does not create it.
            "studio_url": f"https://studio.youtube.com/video/{video_id}/edit",
        }

    def set_thumbnail(self, video_id: str, file_path: str) -> Dict[str, Any]:
        """Attaches a custom thumbnail to a video that is already up.

        A separate call because `videos.insert` has no field for one. It can be
        refused for reasons that have nothing to do with the image — a channel
        without a verified phone number has no custom thumbnails at all — so
        the caller treats a failure here as the upload having succeeded
        without its picture.

        The type is stated rather than guessed from the name: a file the
        `mimetypes` table does not recognise is sent as application/octet-stream,
        which YouTube takes and does nothing with.

        Returns the API response, which carries the URLs of the thumbnail
        YouTube now holds — the only account of what actually landed, since a
        thumbnail set while the video is still being processed is accepted and
        then replaced by the one processing generates.
        """
        mimetype = "image/png" if file_path.lower().endswith(".png") else "image/jpeg"
        return self.service.thumbnails().set(
            videoId=video_id,
            media_body=googleapiclient.http.MediaFileUpload(file_path, mimetype=mimetype),
        ).execute()
