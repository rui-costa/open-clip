from backend.src.services.uploader import Uploader
from backend.src.dataclasses.data import Project
from unittest.mock import MagicMock

def test_uploader_protocol_methods():
    uploader = Uploader()
    project = MagicMock(spec=Project)
    project.step_statuses = {}
    
    # Verify protocol methods exist
    assert hasattr(uploader, 'reset_metadata')
    assert hasattr(uploader, 'start_service')
    assert hasattr(uploader, 'end_service')
    
    # Ensure they execute without failure
    uploader.reset_metadata(project)
    uploader.start_service(project)
    uploader.end_service(project)
    
    assert project.step_statuses["upload"] == "completed"
