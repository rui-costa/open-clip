from backend.src.services.clipper import Clipper
from backend.src.project import Project

def test_clipper_protocol_methods(project_factory):
    """
    Test the protocol methods of the Clipper (reset/start/end).
    """
    clipper = Clipper()
    mock_project = project_factory
    
    # Verify protocol methods are present and callable
    assert hasattr(clipper, 'reset_metadata')
    assert hasattr(clipper, 'start_service')
    assert hasattr(clipper, 'end_service')
    
    # Ensure they execute without failure
    # reset_metadata interacts with the filesystem, so it's tested here
    clipper.reset_metadata(mock_project)
    clipper.start_service(mock_project)
    clipper.end_service(mock_project)
