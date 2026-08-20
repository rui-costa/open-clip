"""Deleting a card in the clip grid removes that highlight and its clip file.

The grid renders one card per highlight — rendered or still a preview — so the
index it sends back is a position in `highlights`. Getting that mapping wrong
deletes somebody else's work.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from backend.src.dataclasses.data import Project

PROJECT_ID = "test-project"


def highlight(text: str, clip: str | None):
    return {
        "highlight_text": text,
        "viral_hook_text": "hook",
        "video_description_for_x": "",
        "video_description_for_reddit": "",
        "video_description_for_linkedin": "",
        "video_title_for_youtube_short": "",
        "start": 0.0,
        "end": 5.0,
        "is_clip_generated": clip is not None,
        "generated_clip_filename": clip,
    }


@pytest.fixture
def project_root(tmp_path, monkeypatch):
    project_dir = tmp_path / "projects" / PROJECT_ID
    (project_dir / "clips").mkdir(parents=True)
    metadata = {
        "project_id": PROJECT_ID,
        "name": "Test Project",
        "created_at": datetime.now().isoformat(),
        "files": {},
        # The unrendered highlight sits between the two rendered ones on
        # purpose: a card index and a "generated clips only" index disagree
        # from position 1 onwards.
        "highlights": [
            highlight("first", "clip_000.mp4"),
            highlight("not rendered yet", None),
            highlight("second", "clip_002.mp4"),
        ],
        "video_metadata": {"components": [], "top_recommendations": []},
        "settings": {"aspect_ratio": "16:9", "resolution": "1080p"},
        "status": None,
        "step_statuses": {},
    }
    (project_dir / "metadata.json").write_text(json.dumps(metadata))
    for name in ("clip_000.mp4", "clip_002.mp4"):
        (project_dir / "clips" / name).write_bytes(b"video")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def read_metadata() -> dict:
    return json.loads((Path("projects") / PROJECT_ID / "metadata.json").read_text())


def clip_path(name: str) -> Path:
    return Path("projects") / PROJECT_ID / "clips" / name


def test_deletes_the_highlight_the_grid_pointed_at(project_root):
    # Index 1 is the unrendered highlight, not the second rendered clip.
    Project(PROJECT_ID).delete_highlight(1)

    stored = read_metadata()["highlights"]
    assert [h["highlight_text"] for h in stored] == ["first", "second"]
    # Neither clip file belonged to the deleted highlight.
    assert clip_path("clip_000.mp4").exists()
    assert clip_path("clip_002.mp4").exists()


def test_deleting_a_rendered_highlight_removes_its_file(project_root):
    Project(PROJECT_ID).delete_highlight(2)

    stored = read_metadata()["highlights"]
    assert [h["highlight_text"] for h in stored] == ["first", "not rendered yet"]
    assert not clip_path("clip_002.mp4").exists()
    assert clip_path("clip_000.mp4").exists()


def test_the_in_memory_project_matches_what_was_written(project_root):
    project = Project(PROJECT_ID)
    project.delete_highlight(0)

    assert [h.highlight_text for h in project.highlights] == ["not rendered yet", "second"]


def test_out_of_range_index_changes_nothing(project_root):
    before = read_metadata()

    with pytest.raises(IndexError):
        Project(PROJECT_ID).delete_highlight(5)

    assert read_metadata() == before
    assert clip_path("clip_000.mp4").exists()


def test_negative_index_changes_nothing(project_root):
    before = read_metadata()

    with pytest.raises(IndexError):
        Project(PROJECT_ID).delete_highlight(-1)

    assert read_metadata() == before


def test_missing_file_on_disk_still_removes_the_entry(project_root):
    clip_path("clip_000.mp4").unlink()

    Project(PROJECT_ID).delete_highlight(0)

    assert len(read_metadata()["highlights"]) == 2


def test_a_concurrent_status_write_is_not_rolled_back(project_root):
    project = Project(PROJECT_ID)  # snapshot taken before the status write
    Project(PROJECT_ID).set_step_status("clipper", "completed")

    project.delete_highlight(0)

    assert read_metadata()["step_statuses"] == {"clipper": "completed"}
