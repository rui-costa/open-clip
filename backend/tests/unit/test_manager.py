import pytest
import os
import shutil
import json
from pathlib import Path
from unittest.mock import MagicMock
from backend.src.manager import ProjectRepository as ProjectManager
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

def test_update_components_persistence(manager):
    """Verify that components dictionary is correctly persisted within video_metadata."""
    project_id = "comp-123"
    manager.create_project(project_id=project_id)

    metadata = manager.get_metadata(project_id)
    if "components" not in metadata.video_metadata:
        metadata.video_metadata["components"] = {}
    metadata.video_metadata["components"]["test_key"] = "test_value"
    manager.save_project_metadata(project_id, metadata)

    # Reload from disk
    reloaded_metadata = manager.get_metadata(project_id)
    assert reloaded_metadata.video_metadata.get("components", {}).get("test_key") == "test_value"

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

# Graceful date and file fallback
def test_graceful_date_and_file_fallback(manager, temp_repo):
    project_id = "malformed-123"
    project_path = temp_repo / project_id
    project_path.mkdir()
    
    metadata_content = {
        "name": "malformed.mp4",
        "settings": {
            "resolution": "keep original",
            "aspect_ratio": "keep original"
        },
        "created_at": "now"
    }
    with open(project_path / "metadata.json", "w") as f:
        json.dump(metadata_content, f)
        
    video_file = project_path / "original.mp4"
    video_file.write_text("fake video data")
    
    metadata = manager.get_metadata(project_id)
    
    assert metadata.project_id == project_id
    assert metadata.name == "malformed.mp4"
    assert metadata.original_file == "original.mp4"
    from datetime import datetime
    assert isinstance(metadata.created_at, datetime)

def test_get_metadata_falls_back_to_scan_when_missing_original_file(temp_repo):
    manager = ProjectManager(base_dir=str(temp_repo))
    # Create a dummy source file for the manager to copy
    source_file = temp_repo / "dummy.txt"
    source_file.write_text("dummy content")
    project_path = manager.create_project(file_path=str(source_file))
    
    # Overwrite metadata to remove original_file
    metadata_path = project_path / "metadata.json"
    data = json.loads(metadata_path.read_text())
    data.pop("original_file", None)
    metadata_path.write_text(json.dumps(data))
    
    # Ensure there is a file matching the pattern in the project directory
    (project_path / "original.txt").write_text("content")
    
    # Now get metadata, should fallback to scanning
    meta = manager.get_metadata(project_path.name)
    assert meta.original_file == "original.txt"
    assert hasattr(meta, "created_at")
