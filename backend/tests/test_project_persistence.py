"""Concurrent steps must not roll each other's writes back.

Steps that share a dependency run in parallel, each holding the Project
snapshot it loaded when it started. A whole-file save from one of them used to
restore every other field to that snapshot, which showed up as a completed step
reappearing as running, its output gone, and a third step back at todo.
"""

import json
import threading
from datetime import datetime
from pathlib import Path

import pytest

from backend.src.dataclasses.data import Project

PROJECT_ID = "test-project"


def write_project(root: Path, step_statuses=None):
    project_dir = root / "projects" / PROJECT_ID
    project_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "project_id": PROJECT_ID,
        "name": "Test Project",
        "created_at": datetime.now().isoformat(),
        "files": {},
        "highlights": [],
        "video_metadata": {"components": [], "top_recommendations": []},
        "settings": {"aspect_ratio": "16:9", "resolution": "1080p"},
        "status": None,
        "step_statuses": step_statuses or {},
    }
    (project_dir / "metadata.json").write_text(json.dumps(metadata))


@pytest.fixture
def project_root(tmp_path, monkeypatch):
    write_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def read_metadata() -> dict:
    return json.loads((Path("projects") / PROJECT_ID / "metadata.json").read_text())


def test_stale_snapshot_does_not_revert_another_steps_status(project_root):
    chapters = Project(PROJECT_ID)
    highlights = Project(PROJECT_ID)  # snapshot taken before chapters finishes

    chapters.set_step_status("chapters", "completed")
    highlights.set_step_status("highlights", "error")

    assert read_metadata()["step_statuses"] == {"chapters": "completed", "highlights": "error"}


def test_stale_snapshot_does_not_delete_another_steps_output(project_root):
    chapters = Project(PROJECT_ID)
    metadata = Project(PROJECT_ID)

    chapters.set_llm_output("chapters", {"chapters": [{"chapter_time": "00:00:00"}]})
    # `metadata` loaded before that write, so its snapshot has no chapters output.
    metadata.set_property("video_metadata", metadata.video_metadata)

    assert "chapters" in read_metadata()["llm_outputs"]


def test_clearing_one_output_leaves_the_others(project_root):
    project = Project(PROJECT_ID)
    project.set_llm_output("chapters", {"a": 1})
    project.set_llm_output("summary", {"b": 2})

    Project(PROJECT_ID).clear_llm_output("chapters")

    assert read_metadata()["llm_outputs"] == {"summary": {"b": 2}}


def test_settings_write_does_not_touch_step_statuses(project_root):
    runner = Project(PROJECT_ID)
    runner.set_step_status("transcription", "completed")

    editor = Project(PROJECT_ID)  # loaded before the status write
    editor.settings.resolution = "720p"
    editor.set_property("settings", editor.settings)

    stored = read_metadata()
    assert stored["settings"]["resolution"] == "720p"
    assert stored["step_statuses"]["transcription"] == "completed"


def test_parallel_status_writes_all_survive(project_root):
    steps = [f"step_{i}" for i in range(12)]
    # Each thread mimics a step holding its own snapshot from before the others wrote.
    projects = [Project(PROJECT_ID) for _ in steps]
    barrier = threading.Barrier(len(steps))

    def run(project, step):
        barrier.wait()
        project.set_step_status(step, "completed")

    threads = [threading.Thread(target=run, args=(p, s)) for p, s in zip(projects, steps)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert read_metadata()["step_statuses"] == {step: "completed" for step in steps}


def test_metadata_file_is_never_left_partially_written(project_root):
    project = Project(PROJECT_ID)
    readers_failed = []
    stop = threading.Event()

    def read_loop():
        while not stop.is_set():
            try:
                json.loads((Path("projects") / PROJECT_ID / "metadata.json").read_text())
            except (json.JSONDecodeError, FileNotFoundError) as e:
                readers_failed.append(e)

    reader = threading.Thread(target=read_loop)
    reader.start()
    try:
        for i in range(50):
            project.set_llm_output("chapters", {"chapters": [{"i": i, "pad": "x" * 500}]})
    finally:
        stop.set()
        reader.join(timeout=5)

    assert readers_failed == []
