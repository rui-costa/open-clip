import pytest
import os
import shutil
import json
from pathlib import Path
from unittest.mock import MagicMock
from backend.src.manager import ProjectManager
from backend.src.exceptions import ProjectNotFoundError

@pytest.fixture
def temp_repo(tmp_path):
    # Setup a temp directory for projects
    base_dir = tmp_path / "projects"
    base_dir.mkdir()
    return base_dir

@pytest.fixture
def manager(temp_repo):
    # Mock repository if needed, but here we can use a real one for integration testing
    return ProjectManager(base_dir=str(temp_repo))

def test_create_project(manager, temp_repo):
    project_path = manager.create_project(project_id="test-123", name="My Project")
    
    assert project_path.exists()
    assert (project_path / "metadata.json").exists()
    
    metadata = manager.get_metadata("test-123")
    assert metadata.name == "My Project"

def test_get_metadata_not_found(manager):
    with pytest.raises(ProjectNotFoundError):
        manager.get_metadata("non-existent")

def test_delete_project(manager):
    manager.create_project(project_id="del-123")
    assert manager.delete_project("del-123") is True
    assert not os.path.exists(manager.get_project_path("del-123"))

def test_update_project_name(manager):
    manager.create_project(project_id="upd-123", name="Old Name")
    manager.update_project_name("upd-123", "New Name")
    metadata = manager.get_metadata("upd-123")
    assert metadata.name == "New Name"

def test_update_metadata_field(manager):
    manager.create_project(project_id="meta-123")
    manager.update_metadata_field("meta-123", "status", "processing")
    metadata = manager.get_metadata("meta-123")
    assert metadata.status == "processing"

def test_save_task_result(manager):
    project_path = manager.create_project(project_id="task-123")
    result_path = manager.save_task_result("task-123", "highlights.json", {"test": "data"})
    assert os.path.exists(result_path)
    metadata = manager.get_metadata("task-123")
    assert metadata.highlights_file == result_path

def test_delete_clip(manager, tmp_path):
    project_path = manager.create_project(project_id="clip-123")
    (project_path / "clips").mkdir(exist_ok=True)
    clip_path = project_path / "clips" / "clip_000.mp4"
    clip_path.write_text("dummy")
    
    highlights_file = project_path / "highlights.json"
    highlights_file.write_text(json.dumps({"highlights": [{"start": 0, "end": 1}]}))
    manager.update_metadata_field("clip-123", "highlights_file", str(highlights_file))
    
    assert manager.delete_clip("clip-123", 0) is True
    assert not clip_path.exists()

# Removed test_get_highlights_not_found because highlights list is now always returned, even if empty.

def test_get_clip_video_path_not_found(manager):
    manager.create_project(project_id="no-clip")
    with pytest.raises(ProjectNotFoundError):
        manager.get_clip_video_path("no-clip", "non-existent.mp4")
