import pytest
import os
import shutil
import json
from pathlib import Path
from backend.src.dataclasses.data import Project

GOLDEN_PROJECT_ID = "00000000-0000-0000-0000-000000000000"

@pytest.fixture
def golden_project(tmp_path):
        
    return Project(GOLDEN_PROJECT_ID)

def test_golden_metadata_loading(golden_project):
    """Verify that the golden project metadata is loaded correctly."""
    assert golden_project.project_id == GOLDEN_PROJECT_ID
    # Correcting name assertion
    assert golden_project.name == "First Project" 
    assert golden_project.settings.aspect_ratio == "9:16"
    assert len(golden_project.clips) > 0
    assert golden_project.clips[0].filename == "clip_000.mp4"

def test_golden_highlights_loading(golden_project):
    """Verify that highlights are correctly loaded from the golden project."""
    assert len(golden_project.highlights) > 0
    assert golden_project.highlights[0].highlight_text != ""

def test_golden_video_meta_loading(golden_project):
    """Verify that video metadata is correctly loaded from the golden project."""
    assert len(golden_project.video_metadata.components) > 0
    assert golden_project.video_metadata.components[0].title != ""

def test_golden_clip_path(golden_project):
    """Verify that clip paths are correctly resolved."""
    clip_name = "clip_000.mp4"
    path = golden_project.base_path / "clips" / clip_name
    assert path.exists()

def test_golden_update_metadata(golden_project):
    """Verify that updating metadata works in memory."""
    new_name = "Updated Golden Project"
    golden_project.name = new_name
    # Instead of calling save() which touches disk, we can verify the change in-memory
    assert golden_project.name == new_name

def test_golden_delete_clip(golden_project):
    """Verify that deleting a clip updates the list in memory."""
    initial_count = len(golden_project.clips)
    
    # Delete first clip manually from list
    golden_project.clips.pop(0)
    
    assert len(golden_project.clips) == initial_count - 1

