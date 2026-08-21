"""Cover for publishing one clip: what it refuses, what it sends, what it records."""

import json
import threading
import time
from datetime import datetime
from pathlib import Path

import pytest

from backend.src.dataclasses.data import Project
from backend.src.infrastructure.youtube_client import ProcessingUnreadableError
from backend.src.orchestrator import ClipRegenerationInProgressError, PipelineOrchestrator
from backend.src.services.uploader import (
    ClipFileMissingError,
    ClipNotPublishedError,
    ClipNotRenderedError,
    UploadInProgressError,
    Uploader,
)

PIPELINE_CONFIG = Path(__file__).resolve().parents[1] / "config" / "pipeline.json"

PROJECT_ID = "test-project"


class FakeClipper:
    """Stands in for the cut every upload now begins with.

    Writes the file the uploader is about to send and records the highlight it
    was asked for, so a test can say whether the clip was cut afresh rather than
    picked up off disk.
    """

    def __init__(self, project_dir: Path, error: Exception = None, writes: bool = True):
        self.calls = []
        self.error = error
        self.writes = writes
        self.project_dir = project_dir

    def render_one(self, project, index):
        self.calls.append(index)
        if self.error:
            raise self.error
        if not self.writes:
            return {}
        filename = f"clip_{index:03d}.mp4"
        write_clip(self.project_dir, filename, b"the cut this upload made")
        highlights = project.highlights
        highlights[index].is_clip_generated = True
        highlights[index].generated_clip_filename = filename
        highlights[index].rendered_at = datetime.now().isoformat()
        project.set_property("highlights", highlights)
        return highlights[index].to_dict()


def uploader(project_dir: Path, **overrides) -> Uploader:
    """An uploader whose cut is a fake, which is every test that publishes."""
    options = {"clipper": FakeClipper(project_dir)}
    options.update(overrides)
    return Uploader(**options)


class FakeYoutube:
    """Stands in for the API handle. Records what it was asked to publish."""

    def __init__(self):
        self.calls = []
        self.thumbnails = []
        # Set to make the thumbnail call fail the way YouTube does for a
        # channel with no custom thumbnails.
        self.thumbnail_error = None
        # Called after a thumbnail is recorded, so a test can wait for one that
        # is set from the retry thread rather than from the upload.
        self.on_thumbnail = None
        # What `processing_status` answers, one call at a time; the last answer
        # stands for every call after it. `None` there means the video is gone.
        self.processing = ["succeeded"]
        self.processing_error = None
        self.status_calls = 0
        # What `video_exists` answers. None is "could not ask" — no read scope,
        # no network, a quota refusal — which is not the same as a "no".
        self.exists = True
        self.exists_calls = []
        self.started = threading.Event()
        self.release = threading.Event()
        self.block = False

    def upload_video(self, file_path, title, description):
        self.calls.append({"file_path": file_path, "title": title, "description": description})
        if self.block:
            self.started.set()
            self.release.wait(timeout=5)
        return {"video_id": "vid-1", "url": "https://youtube.com/watch?v=vid-1"}

    def processing_status(self, video_id):
        if self.processing_error:
            raise self.processing_error
        answer = self.processing[min(self.status_calls, len(self.processing) - 1)]
        self.status_calls += 1
        return answer

    def video_exists(self, video_id):
        self.exists_calls.append(video_id)
        return self.exists

    def set_thumbnail(self, video_id, file_path):
        if self.thumbnail_error:
            raise RuntimeError(self.thumbnail_error)
        self.thumbnails.append({"video_id": video_id, "file_path": file_path})
        if self.on_thumbnail:
            self.on_thumbnail()
        return {"items": [{"default": {"url": "https://i.ytimg.com/vi/vid-1/default.jpg"}}]}


def highlight(**overrides):
    data = {
        "highlight_text": "the quote",
        "viral_hook_text": "the hook",
        "video_title_for_youtube_short": "The Title",
        "video_description_for_youtube_short": "what the short is about",
        "video_description_for_x": "",
        "video_description_for_reddit": "",
        "video_description_for_linkedin": "",
        "start": 0,
        "end": 30,
        "is_clip_generated": True,
        "generated_clip_filename": "clip_000.mp4",
    }
    data.update(overrides)
    return data


def write_project(root: Path, highlights, description=None):
    project_dir = root / "projects" / PROJECT_ID
    project_dir.mkdir(parents=True, exist_ok=True)
    (project_dir / "metadata.json").write_text(json.dumps({
        "project_id": PROJECT_ID,
        "name": "Test Project",
        "created_at": datetime.now().isoformat(),
        "files": {},
        "highlights": highlights,
        "video_metadata": {"components": [], "top_recommendations": []},
        "settings": {
            "aspect_ratio": "9:16",
            "resolution": "1080p",
            "description": description or {},
        },
        "status": None,
        "step_statuses": {},
    }))
    return project_dir


def write_clip(project_dir: Path, filename="clip_000.mp4", content=b"not really an mp4"):
    clips = project_dir / "clips"
    clips.mkdir(exist_ok=True)
    (clips / filename).write_bytes(content)


@pytest.fixture
def project_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


def read_metadata() -> dict:
    return json.loads((Path("projects") / PROJECT_ID / "metadata.json").read_text())


def test_a_clip_nobody_has_rendered_is_cut_and_then_published(project_root):
    # The clipper is not a step an upload waits for any more: a highlight the
    # user never rendered is cut on its way up.
    project_dir = write_project(
        project_root, [highlight(is_clip_generated=False, generated_clip_filename=None)]
    )
    clipper = FakeClipper(project_dir)
    client = FakeYoutube()

    result = uploader(project_dir, clipper=clipper).upload_one(Project(PROJECT_ID), 0, client=client)

    assert clipper.calls == [0]
    assert result["url"] == "https://youtube.com/watch?v=vid-1"
    assert client.calls[0]["file_path"].endswith("clips/clip_000.mp4")


def test_a_clip_that_already_has_a_file_is_cut_again_before_it_goes_up(project_root):
    # What the page shows is drawn from the settings as they stand now, so a
    # file cut before the last caption or title change is a different clip. The
    # upload is what makes the two the same.
    project_dir = write_project(project_root, [highlight()])
    write_clip(project_dir, content=b"the cut from before the last change")
    clipper = FakeClipper(project_dir)
    client = FakeYoutube()

    uploader(project_dir, clipper=clipper).upload_one(Project(PROJECT_ID), 0, client=client)

    assert clipper.calls == [0]
    assert (project_dir / "clips" / "clip_000.mp4").read_bytes() == b"the cut this upload made"


def test_a_render_that_produced_no_file_publishes_nothing(project_root):
    project_dir = write_project(project_root, [highlight()])  # metadata says rendered, no file
    client = FakeYoutube()

    with pytest.raises(ClipFileMissingError):
        uploader(project_dir, clipper=FakeClipper(project_dir, writes=False)).upload_one(
            Project(PROJECT_ID), 0, client=client
        )

    assert client.calls == []


def test_a_render_that_left_the_highlight_uncut_publishes_nothing(project_root):
    project_dir = write_project(
        project_root, [highlight(is_clip_generated=False, generated_clip_filename=None)]
    )
    client = FakeYoutube()

    with pytest.raises(ClipNotRenderedError):
        uploader(project_dir, clipper=FakeClipper(project_dir, writes=False)).upload_one(
            Project(PROJECT_ID), 0, client=client
        )

    assert client.calls == []


def test_a_render_that_fell_over_publishes_nothing(project_root):
    project_dir = write_project(project_root, [highlight()])
    write_clip(project_dir)  # the previous cut, which must not be published in its place
    client = FakeYoutube()
    failing = FakeClipper(project_dir, error=FileNotFoundError("The source video is missing."))

    with pytest.raises(FileNotFoundError):
        uploader(project_dir, clipper=failing).upload_one(Project(PROJECT_ID), 0, client=client)

    assert client.calls == []


def test_no_highlight_at_that_index_raises_index_error(project_root):
    project_dir = write_project(project_root, [highlight()])
    clipper = FakeClipper(project_dir)

    with pytest.raises(IndexError):
        uploader(project_dir, clipper=clipper).upload_one(Project(PROJECT_ID), 7, client=FakeYoutube())

    # Refused before the expensive part, not after it.
    assert clipper.calls == []


def test_upload_sends_the_youtube_title_and_the_built_description(project_root):
    project_dir = write_project(
        project_root,
        [highlight()],
        description={"source_title": "The Podcast", "source_url": "https://youtu.be/abc123"},
    )
    client = FakeYoutube()

    result = uploader(project_dir).upload_one(Project(PROJECT_ID), 0, client=client)

    assert result["url"] == "https://youtube.com/watch?v=vid-1"
    sent = client.calls[0]
    assert sent["title"] == "The Title"
    assert sent["file_path"].endswith("projects/test-project/clips/clip_000.mp4")
    # The description is the template's output, not one model field.
    assert sent["description"].startswith("what the short is about")
    assert "The Podcast" in sent["description"]
    assert "https://youtu.be/abc123" in sent["description"]


class FakeThumbnailer:
    """Stands in for the renderer. Records every render it is asked for."""

    RENDERED = b"a thumbnail this renderer made"

    def __init__(self, project_dir: Path, fails: bool = False):
        self.calls = []
        self.fails = fails
        self.project_dir = project_dir

    def generate(self, project, index):
        self.calls.append(index)
        if self.fails:
            raise RuntimeError("the frame could not be taken")
        directory = self.project_dir / "thumbnails"
        directory.mkdir(exist_ok=True)
        (directory / f"clip_{index:03d}.jpg").write_bytes(self.RENDERED)

    def path(self, project, highlight):
        made = self.project_dir / "thumbnails" / "clip_000.jpg"
        return made if made.exists() else None


def write_thumbnail(project_dir: Path, content: bytes = b"the picture the user made"):
    directory = project_dir / "thumbnails"
    directory.mkdir(exist_ok=True)
    path = directory / "clip_000.jpg"
    path.write_bytes(content)
    return path


def test_the_thumbnail_on_disk_is_the_one_that_gets_uploaded(project_root):
    # The file in the project is the picture the user made and can look at.
    # Rendering a fresh one at upload sent something else and overwrote the
    # file with it, which hid the difference the moment it happened.
    project_dir = write_project(project_root, [highlight()])
    made_earlier = write_thumbnail(project_dir)
    client = FakeYoutube()
    thumbnails = FakeThumbnailer(project_dir)

    result = uploader(
        project_dir, thumbnailer=thumbnails, thumbnail_retry_delays=(), poll_limit=0
    ).upload_one(Project(PROJECT_ID), 0, client=client)

    assert thumbnails.calls == [], "the thumbnail on disk was re-rendered"
    assert made_earlier.read_bytes() == b"the picture the user made"
    assert result["thumbnail_set"] is True
    assert client.thumbnails[0]["file_path"] == str(made_earlier)


def test_a_published_clip_can_be_given_its_thumbnail_again(project_root):
    # For a picture changed after the clip went up, and for the clips published
    # before the uploader sent the file on disk at all. The video is not
    # touched: same id, same views.
    project_dir = write_project(
        project_root, [highlight(youtube_video_id="vid-1", youtube_url="https://youtu.be/vid-1")]
    )
    made_earlier = write_thumbnail(project_dir)
    client = FakeYoutube()
    thumbnails = FakeThumbnailer(project_dir)

    result = uploader(
        project_dir, thumbnailer=thumbnails, thumbnail_retry_delays=(), poll_limit=0
    ).upload_thumbnail(Project(PROJECT_ID), 0, client=client)

    assert result["thumbnail_set"] is True
    assert result["video_id"] == "vid-1"
    assert client.thumbnails[0]["file_path"] == str(made_earlier)
    assert thumbnails.calls == []
    # Nothing was published: this only changes the still.
    assert client.calls == []


# Nothing tells this application when a video it published is deleted on
# YouTube. Without a check the record outlives the video: a dead link on the
# clip page, and a thumbnail sent against an id that addresses nothing.


def test_a_video_deleted_on_youtube_takes_its_record_with_it(project_root):
    project_dir = write_project(
        project_root, [highlight(youtube_video_id="vid-1", youtube_url="https://youtu.be/vid-1")]
    )
    client = FakeYoutube()
    client.exists = False

    gone = uploader(project_dir).verify_publication(Project(PROJECT_ID), 0, client=client)

    assert gone is False
    stored = Project(PROJECT_ID).highlights[0]
    # The clip reads as unpublished everywhere now, and can be published again
    # as though for the first time.
    assert stored.youtube_video_id is None
    assert stored.youtube_url is None
    assert stored.uploaded_at is None


def test_a_video_that_is_still_there_is_left_alone(project_root):
    project_dir = write_project(
        project_root, [highlight(youtube_video_id="vid-1", youtube_url="https://youtu.be/vid-1")]
    )
    client = FakeYoutube()
    client.exists = True

    assert uploader(project_dir).verify_publication(Project(PROJECT_ID), 0, client=client) is True
    assert Project(PROJECT_ID).highlights[0].youtube_video_id == "vid-1"


def test_not_being_able_to_ask_is_not_a_no(project_root):
    # No read scope, no network, a quota refusal. Clearing a good record on the
    # strength of a question that could not be asked would lose the link to a
    # video that is still there.
    project_dir = write_project(
        project_root, [highlight(youtube_video_id="vid-1", youtube_url="https://youtu.be/vid-1")]
    )
    client = FakeYoutube()
    client.exists = None

    assert uploader(project_dir).verify_publication(Project(PROJECT_ID), 0, client=client) is None
    assert Project(PROJECT_ID).highlights[0].youtube_video_id == "vid-1"


def test_a_thumbnail_is_not_sent_to_a_video_that_is_gone(project_root):
    project_dir = write_project(
        project_root, [highlight(youtube_video_id="vid-1", youtube_url="https://youtu.be/vid-1")]
    )
    write_thumbnail(project_dir)
    client = FakeYoutube()
    client.exists = False

    with pytest.raises(ClipNotPublishedError) as failure:
        uploader(
            project_dir,
            thumbnailer=FakeThumbnailer(project_dir),
            thumbnail_retry_delays=(),
            poll_limit=0,
        ).upload_thumbnail(Project(PROJECT_ID), 0, client=client)

    # The message has to say what to do about it, not just that it failed.
    assert "no longer on YouTube" in str(failure.value)
    assert "Upload the clip again" in str(failure.value)
    # And nothing was sent.
    assert client.thumbnails == []


def test_a_clip_that_was_never_published_has_no_video_to_set_one_on(project_root):
    project_dir = write_project(project_root, [highlight()])
    write_thumbnail(project_dir)

    with pytest.raises(ClipNotPublishedError):
        uploader(
            project_dir,
            thumbnailer=FakeThumbnailer(project_dir),
            thumbnail_retry_delays=(),
            poll_limit=0,
        ).upload_thumbnail(Project(PROJECT_ID), 0, client=FakeYoutube())


def test_a_clip_with_no_thumbnail_yet_gets_one_rendered(project_root):
    # Publishing without a picture leaves YouTube to pick a frame, so a clip
    # nobody made a thumbnail for still gets one.
    project_dir = write_project(project_root, [highlight()])
    client = FakeYoutube()
    thumbnails = FakeThumbnailer(project_dir)

    result = uploader(
        project_dir, thumbnailer=thumbnails, thumbnail_retry_delays=(), poll_limit=0
    ).upload_one(Project(PROJECT_ID), 0, client=client)

    assert thumbnails.calls == [0]
    assert result["thumbnail_set"] is True
    assert client.thumbnails[0]["video_id"] == "vid-1"
    assert client.thumbnails[0]["file_path"].endswith("thumbnails/clip_000.jpg")


def test_a_thumbnail_that_will_not_render_does_not_fail_the_upload(project_root):
    project_dir = write_project(project_root, [highlight()])
    client = FakeYoutube()

    result = uploader(
        project_dir,
        thumbnailer=FakeThumbnailer(project_dir, fails=True),
        thumbnail_retry_delays=(),
        poll_limit=0,
    ).upload_one(Project(PROJECT_ID), 0, client=client)

    assert result["url"] == "https://youtube.com/watch?v=vid-1"
    assert result["thumbnail_set"] is False
    assert client.thumbnails == []


def test_a_thumbnail_that_will_not_attach_does_not_fail_the_upload(project_root):
    # The video is live by the time the thumbnail is set, and an unverified
    # channel is not something this app can do anything about.
    project_dir = write_project(project_root, [highlight()])
    client = FakeYoutube()
    client.thumbnail_error = "The channel is not enabled for custom thumbnails."

    result = uploader(
        project_dir,
        thumbnailer=FakeThumbnailer(project_dir),
        thumbnail_retry_delays=(),
        poll_limit=0,
    ).upload_one(Project(PROJECT_ID), 0, client=client)

    assert result["url"] == "https://youtube.com/watch?v=vid-1"
    assert result["thumbnail_set"] is False
    assert read_metadata()["highlights"][0]["youtube_video_id"] == "vid-1"


def retrying_uploader(project_dir, later, **overrides):
    """An uploader whose re-set thread runs at test speed."""
    options = {
        "thumbnailer": FakeThumbnailer(project_dir),
        "client_factory": lambda: later,
        "poll_seconds": 0.01,
        "poll_limit": 20,
    }
    options.update(overrides)
    return uploader(project_dir, **options)


def test_the_thumbnail_is_set_again_once_processing_has_finished(project_root):
    # The set made straight after the upload is accepted and then overwritten
    # by the thumbnail YouTube generates when it finishes processing. So the
    # same picture is sent again, on a thread of its own, and only once YouTube
    # has said it is done.
    project_dir = write_project(project_root, [highlight()])
    write_clip(project_dir)
    client = FakeYoutube()
    later = FakeYoutube()
    later.processing = ["processing", "processing", "succeeded"]
    done = threading.Event()
    later.on_thumbnail = done.set

    retrying_uploader(project_dir, later).upload_one(Project(PROJECT_ID), 0, client=client)

    assert done.wait(timeout=5), "the thumbnail was never set a second time"
    assert later.thumbnails[0]["video_id"] == "vid-1"
    assert later.status_calls == 3
    # A fresh handle, not the one the upload went through: two threads cannot
    # share one googleapiclient service.
    assert len(client.thumbnails) == 1


def test_a_video_that_failed_processing_is_left_alone(project_root):
    project_dir = write_project(project_root, [highlight()])
    write_clip(project_dir)
    later = FakeYoutube()
    later.processing = ["processing", "failed"]

    retrying_uploader(project_dir, later).upload_one(
        Project(PROJECT_ID), 0, client=FakeYoutube()
    )

    time.sleep(0.3)
    assert later.thumbnails == []


def test_a_token_that_cannot_read_processing_falls_back_to_timed_retries(project_root):
    # A channel authorised before the readonly scope was asked for still
    # uploads; it just cannot be told when the picture is safe to attach.
    project_dir = write_project(project_root, [highlight()])
    write_clip(project_dir)
    later = FakeYoutube()
    later.processing_error = ProcessingUnreadableError("no readonly scope")
    done = threading.Event()
    later.on_thumbnail = done.set

    retrying_uploader(project_dir, later, thumbnail_retry_delays=(0, 0)).upload_one(
        Project(PROJECT_ID), 0, client=FakeYoutube()
    )

    assert done.wait(timeout=5), "the thumbnail was never set a second time"
    time.sleep(0.2)
    assert len(later.thumbnails) == 2


def test_a_deleted_thumbnail_is_not_sent_again(project_root):
    project_dir = write_project(project_root, [highlight()])
    write_clip(project_dir)
    later = FakeYoutube()
    # Long enough for the file to go while the thread is still waiting.
    later.processing = ["processing"] * 5 + ["succeeded"]

    retrying_uploader(project_dir, later, poll_seconds=0.1).upload_one(
        Project(PROJECT_ID), 0, client=FakeYoutube()
    )
    (project_dir / "thumbnails" / "clip_000.jpg").unlink()

    time.sleep(0.9)
    assert later.thumbnails == []


def test_the_hook_is_the_title_only_when_no_youtube_title_was_written(project_root):
    project_dir = write_project(project_root, [highlight(video_title_for_youtube_short="")])
    client = FakeYoutube()

    uploader(project_dir).upload_one(Project(PROJECT_ID), 0, client=client)

    assert client.calls[0]["title"] == "the hook"


def test_the_published_video_is_recorded_on_the_highlight(project_root):
    project_dir = write_project(
        project_root,
        # Carrying the reason the last attempt gave up, which this one answers.
        [highlight(upload_error="YouTube would not take it.")],
    )

    uploader(project_dir).upload_one(Project(PROJECT_ID), 0, client=FakeYoutube())

    stored = read_metadata()["highlights"][0]
    assert stored["youtube_video_id"] == "vid-1"
    assert stored["youtube_url"] == "https://youtube.com/watch?v=vid-1"
    assert stored["uploaded_at"]
    # A live video sitting next to an error message reads as one.
    assert stored["upload_error"] is None
    # And it survives a reload, so the clip page can say the clip is live.
    assert Project(PROJECT_ID).highlights[0].youtube_url == "https://youtube.com/watch?v=vid-1"


def wait_for(predicate, timeout=5.0, interval=0.02):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def publishing_orchestrator(project_dir, client, clipper=None) -> PipelineOrchestrator:
    """An orchestrator whose upload cuts a fake clip and talks to a fake YouTube."""
    service = uploader(
        project_dir,
        clipper=clipper or FakeClipper(project_dir),
        thumbnailer=FakeThumbnailer(project_dir),
        thumbnail_retry_delays=(),
        poll_limit=0,
        client_factory=lambda: client,
    )
    return PipelineOrchestrator(config_path=str(PIPELINE_CONFIG), services={"upload": service})


def test_orchestrator_publishes_through_the_upload_service(project_root):
    project_dir = write_project(project_root, [highlight()])
    client = FakeYoutube()
    orchestrator = publishing_orchestrator(project_dir, client)

    job = orchestrator.upload_clip(PROJECT_ID, 0)

    # A key to watch, not an outcome: the cut this begins with outlives the
    # request that asked for it.
    assert job == f"{PROJECT_ID}_upload_clip_0"
    assert job in orchestrator.active_processes
    assert wait_for(lambda: not orchestrator.active_processes)
    # The outcome is on the highlight, which is where the page reads it.
    assert read_metadata()["highlights"][0]["youtube_url"] == "https://youtube.com/watch?v=vid-1"


def test_why_an_upload_published_nothing_is_written_onto_the_clip(project_root):
    project_dir = write_project(project_root, [highlight()])
    client = FakeYoutube()
    orchestrator = publishing_orchestrator(
        project_dir,
        client,
        clipper=FakeClipper(project_dir, error=RuntimeError("The source video is missing.")),
    )

    orchestrator.upload_clip(PROJECT_ID, 0)

    assert wait_for(lambda: not orchestrator.active_processes)
    stored = read_metadata()["highlights"][0]
    assert stored["upload_error"] == "The source video is missing."
    assert stored["youtube_url"] is None
    assert client.calls == []


def test_an_authorisation_that_cannot_publish_is_refused_before_anything_is_cut(project_root):
    project_dir = write_project(project_root, [highlight()])
    clipper = FakeClipper(project_dir)
    service = uploader(
        project_dir,
        clipper=clipper,
        client_factory=lambda: (_ for _ in ()).throw(RuntimeError("No credentials.")),
    )
    orchestrator = PipelineOrchestrator(
        config_path=str(PIPELINE_CONFIG), services={"upload": service}
    )

    with pytest.raises(RuntimeError):
        orchestrator.upload_clip(PROJECT_ID, 0)

    assert clipper.calls == []
    # And the registration goes with it, so the next attempt is not refused as
    # a duplicate of one that never started.
    assert orchestrator.active_processes == {}


def test_a_second_request_for_the_same_clip_is_refused_while_one_is_running(project_root):
    project_dir = write_project(project_root, [highlight()])
    client = FakeYoutube()
    client.block = True
    orchestrator = publishing_orchestrator(project_dir, client)

    orchestrator.upload_clip(PROJECT_ID, 0)
    assert client.started.wait(timeout=5)

    try:
        with pytest.raises(UploadInProgressError):
            orchestrator.upload_clip(PROJECT_ID, 0)
    finally:
        client.release.set()

    assert wait_for(lambda: not orchestrator.active_processes)
    # One upload, not two.
    assert len(client.calls) == 1


def test_a_clip_being_uploaded_cannot_be_re_cut_at_the_same_time(project_root):
    # The upload cuts the clip itself, into the file a re-cut would write.
    project_dir = write_project(project_root, [highlight()])
    client = FakeYoutube()
    client.block = True
    orchestrator = publishing_orchestrator(project_dir, client)

    orchestrator.upload_clip(PROJECT_ID, 0)
    assert client.started.wait(timeout=5)

    try:
        with pytest.raises(UploadInProgressError):
            orchestrator.regenerate_clip(PROJECT_ID, 0)
    finally:
        client.release.set()

    assert wait_for(lambda: not orchestrator.active_processes)


def test_a_clip_being_re_cut_cannot_be_uploaded_at_the_same_time(project_root):
    project_dir = write_project(project_root, [highlight()])
    orchestrator = publishing_orchestrator(project_dir, FakeYoutube())
    orchestrator.active_processes[f"{PROJECT_ID}_clip_0"] = time.time()

    with pytest.raises(ClipRegenerationInProgressError):
        orchestrator.upload_clip(PROJECT_ID, 0)


def test_no_highlight_at_that_index_is_refused_before_a_job_is_registered(project_root):
    project_dir = write_project(project_root, [highlight()])
    orchestrator = publishing_orchestrator(project_dir, FakeYoutube())

    with pytest.raises(IndexError):
        orchestrator.upload_clip(PROJECT_ID, 7)

    assert orchestrator.active_processes == {}
