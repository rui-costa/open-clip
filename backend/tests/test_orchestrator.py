import json
import threading
import time
from datetime import datetime
from pathlib import Path

import pytest

from backend.src.orchestrator import PipelineOrchestrator

PIPELINE_CONFIG = Path(__file__).resolve().parents[1] / "config" / "pipeline.json"

PROJECT_ID = "test-project"


class BlockingService:
    """Service whose execute() blocks until the test releases it."""

    def __init__(self):
        self.started = threading.Event()
        self.release = threading.Event()
        self.calls = 0

    def execute(self, project):
        self.calls += 1
        self.started.set()
        self.release.wait(timeout=5)


def write_project(root: Path, step_statuses=None):
    project_dir = root / "projects" / PROJECT_ID
    project_dir.mkdir(parents=True)
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


def make_orchestrator(services):
    return PipelineOrchestrator(config_path=str(PIPELINE_CONFIG), services=services)


def test_run_step_registers_process_before_returning(project_root):
    service = BlockingService()
    orchestrator = make_orchestrator({"clipper": service})

    orchestrator.run_step(PROJECT_ID, "clipper")

    # The frontend gates its polling on this list, so the key has to be there
    # by the time the triggering request returns, not once the thread starts.
    assert f"{PROJECT_ID}_clipper" in orchestrator.active_processes

    service.release.set()
    orchestrator.active_project_orchestrators[PROJECT_ID].join(timeout=5)
    assert orchestrator.active_processes == {}


def test_run_step_clears_process_when_service_raises(project_root):
    class FailingService:
        def execute(self, project):
            raise RuntimeError("boom")

    orchestrator = make_orchestrator({"clipper": FailingService()})

    orchestrator.run_step(PROJECT_ID, "clipper")
    orchestrator.active_project_orchestrators[PROJECT_ID].join(timeout=5)

    assert orchestrator.active_processes == {}


def test_run_step_ignores_duplicate_trigger_while_running(project_root):
    service = BlockingService()
    orchestrator = make_orchestrator({"clipper": service})

    orchestrator.run_step(PROJECT_ID, "clipper")
    assert service.started.wait(timeout=5)
    orchestrator.run_step(PROJECT_ID, "clipper")

    service.release.set()
    orchestrator.active_project_orchestrators[PROJECT_ID].join(timeout=5)
    assert service.calls == 1


def test_run_pipeline_registers_pipeline_and_step_processes(project_root):
    service = BlockingService()
    orchestrator = make_orchestrator({"transcription": service})

    orchestrator.run_pipeline(PROJECT_ID)

    # The pipeline registration is what keeps the UI polling across the gaps
    # between individual steps.
    assert f"{PROJECT_ID}_pipeline" in orchestrator.active_processes
    assert service.started.wait(timeout=5)
    assert f"{PROJECT_ID}_transcription" in orchestrator.active_processes

    # Mark everything done on disk so the runner loop exits, then release.
    metadata_path = project_root / "projects" / PROJECT_ID / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    steps = json.loads(PIPELINE_CONFIG.read_text())["steps"]
    metadata["step_statuses"] = {step: "completed" for step in steps}
    metadata_path.write_text(json.dumps(metadata))
    service.release.set()

    assert wait_for(lambda: not orchestrator.active_processes)


def wait_for(predicate, timeout=5.0, interval=0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


class RecordingService:
    """Service that records whether the orchestrator reset it."""

    def __init__(self):
        self.reset_calls = 0

    def reset_metadata(self, project):
        self.reset_calls += 1

    def execute(self, project):
        pass


def write_statuses(root: Path, statuses: dict):
    metadata_path = root / "projects" / PROJECT_ID / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["step_statuses"] = statuses
    metadata_path.write_text(json.dumps(metadata))


def read_statuses(root: Path) -> dict:
    return json.loads((root / "projects" / PROJECT_ID / "metadata.json").read_text())["step_statuses"]


def test_rerunning_a_step_resets_everything_downstream(project_root):
    """Re-running highlights must not leave the clipper showing "done".

    Every clip is cut from the highlight list this step is about to replace, so
    those clips stop existing the moment highlights re-runs.
    """
    clipper = RecordingService()
    upload = RecordingService()
    orchestrator = make_orchestrator({
        "highlights": RecordingService(),
        "clipper": clipper,
        "upload": upload,
    })
    write_statuses(project_root, {
        "transcription": "completed",
        "highlights": "completed",
        "clipper": "completed",
        "upload": "completed",
    })

    orchestrator.run_step(PROJECT_ID, "highlights")
    orchestrator.active_project_orchestrators[PROJECT_ID].join(timeout=5)

    statuses = read_statuses(project_root)
    # Both are cut from the highlight list this step replaces, so both are stale.
    assert statuses["clipper"] == "todo"
    assert statuses["upload"] == "todo"
    # Untouched: transcription is what highlights reads, not what it feeds.
    assert statuses["transcription"] == "completed"
    assert clipper.reset_calls == 1
    assert upload.reset_calls == 1


def test_rerunning_a_step_leaves_downstream_steps_that_never_ran(project_root):
    clipper = RecordingService()
    orchestrator = make_orchestrator({"highlights": RecordingService(), "clipper": clipper})
    write_statuses(project_root, {"transcription": "completed", "highlights": "completed"})

    orchestrator.run_step(PROJECT_ID, "highlights")
    orchestrator.active_project_orchestrators[PROJECT_ID].join(timeout=5)

    # Nothing to invalidate: wiping the clips directory of a step that has no
    # output is pure risk.
    assert clipper.reset_calls == 0
