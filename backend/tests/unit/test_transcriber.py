from backend.src.services.transcriber import Transcriber
from backend.src.project import Project
import os

def test_transcriber_reset_metadata_with_files(golden_project):
    """
    Test reset_metadata using the golden project fixture.
    """
    t = Transcriber()
    
    # Create the files expected by _get_paths to exist
    txt_path = os.path.join(os.path.dirname(str(golden_project.files.original_file)), "transcription.txt")
    csv_path = os.path.join(os.path.dirname(str(golden_project.files.original_file)), "word_map.csv")
    
    with open(txt_path, 'w') as f: f.write("test")
    with open(csv_path, 'w') as f: f.write("test")
    
    try:
        t.reset_metadata(golden_project)
        
        # Verify files were removed
        assert not os.path.exists(txt_path)
        assert not os.path.exists(csv_path)
    finally:
        # Cleanup in case the test failed
        if os.path.exists(txt_path): os.remove(txt_path)
        if os.path.exists(csv_path): os.remove(csv_path)

def test_transcriber_protocol_methods(golden_project):
    """
    Test the non-skipped protocol methods of the Transcriber.
    """
    t = Transcriber()
    
    # Verify protocol methods are present and callable
    assert hasattr(t, 'reset_metadata')
    assert hasattr(t, 'start_service')
    assert hasattr(t, 'end_service')
    
    # Ensure they execute without failure
    t.start_service(golden_project)
    t.end_service(golden_project)
