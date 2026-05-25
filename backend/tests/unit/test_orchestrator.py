import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json
import os
import datetime
import time

# Mock Args class for CLI handlers
class MockArgs:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

# Temporarily ensure backend is in path for imports during testing
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.absolute()))

from backend.src.orchestrator import PipelineOrchestrator
from backend.src.manager import ProjectManager
from backend.src.models import ProjectMetadata

class TestPipelineOrchestrator(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path("test_projects")
        self.test_dir.mkdir(exist_ok=True)
        self.project_id = "test_project"
        self.project_path = self.test_dir / self.project_id
        self.project_path.mkdir(exist_ok=True)

        self.metadata_path = self.project_path / "metadata.json"
        self.initial_metadata = {
            "project_id": self.project_id,
            "name": "Test Project",
            "original_file": "episode.mp4",
            "transcription_file": None,
            "highlights": [],
            "video_metadata": {},
            "components": {
                "word_map_file": None
            },
            "settings": {
                "aspect_ratio": "16:9",
                "resolution": "1080p"
            },
            "created_at": "2023-01-01T12:00:00Z"
        }
        with open(self.metadata_path, 'w') as f:
            json.dump(self.initial_metadata, f)

        self.config_path = self.test_dir / "pipeline.json"
        self.pipeline_config_content = {
            "execution_order": ["transcribe", "highlights", "metadata", "clipper", "upload"],
            "steps": {
                "transcribe": {"command": "transcribe", "depends_on": []},
                "highlights": {"command": "highlights", "depends_on": ["transcribe"]},
                "metadata": {"command": "metadata", "depends_on": ["transcribe"]},
                "clipper": {"command": "clipper", "depends_on": ["highlights", "metadata"]},
                "upload": {"command": "upload", "depends_on": ["clipper"]}
            }
        }
        with open(self.config_path, 'w') as f:
            json.dump(self.pipeline_config_content, f)

        self.orchestrator = PipelineOrchestrator(
            projects_base_dir=str(self.test_dir),
            config_path=str(self.config_path)
        )

        self.mock_metadata = ProjectMetadata(**self.initial_metadata)
        self.orchestrator.project_manager = MagicMock(spec=ProjectManager)
        self.orchestrator.project_manager.get_project_path.return_value = str(self.project_path)
        self.orchestrator.project_manager.get_metadata.return_value = self.mock_metadata
        self.orchestrator.project_manager.update_step_status = MagicMock()
        self.orchestrator.project_manager.save_project_metadata = MagicMock()
        self.orchestrator.project_manager.save_highlights = MagicMock()

    def tearDown(self):
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        
        if str(Path(__file__).parent.parent.parent.absolute()) in sys.path:
            sys.path.remove(str(Path(__file__).parent.parent.parent.absolute()))

    def test_is_step_complete(self):
        self.assertFalse(self.orchestrator.is_step_complete(self.project_id, "transcribe"))
        (self.project_path / "transcription.txt").write_text("test")
        self.assertTrue(self.orchestrator.is_step_complete(self.project_id, "transcribe"))

        self.assertFalse(self.orchestrator.is_step_complete(self.project_id, "highlights"))
        self.mock_metadata.highlights = [{"text": "highlight"}]
        self.assertTrue(self.orchestrator.is_step_complete(self.project_id, "highlights"))

    def test_get_eligible_steps(self):
        eligible = self.orchestrator._get_eligible_steps(self.project_id)
        self.assertIn("transcribe", eligible)
        self.assertNotIn("highlights", eligible)

        (self.project_path / "transcription.txt").write_text("test")
        self.orchestrator.reload_config()
        eligible = self.orchestrator._get_eligible_steps(self.project_id)
        self.assertIn("highlights", eligible)
        self.assertIn("metadata", eligible)

    @patch('backend.cli.handle_transcribe')
    @patch('backend.cli.handle_highlights')
    @patch('backend.cli.handle_metadata')
    @patch('backend.cli.handle_clipper')
    @patch('backend.cli.handle_upload')
    def test_run_single_step_updates_status(self, mock_handle_upload, mock_handle_clipper, mock_handle_metadata, mock_handle_highlights, mock_handle_transcribe):
        mock_handle_metadata.return_value = None
        self.orchestrator._run_single_step(self.project_id, "metadata")
        mock_handle_metadata.assert_called_once()
        self.orchestrator.project_manager.update_step_status.assert_called_with(
            self.project_id, "metadata", status="completed"
        )

        mock_handle_transcribe.side_effect = Exception("Transcribe failed")
        self.orchestrator._run_single_step(self.project_id, "transcribe")
        mock_handle_transcribe.assert_called_once()
        self.orchestrator.project_manager.update_step_status.assert_called_with(
            self.project_id, "transcribe", status="failed"
        )

    @patch('backend.cli.handle_transcribe')
    @patch('backend.cli.handle_highlights')
    @patch('backend.cli.handle_metadata')
    @patch('backend.cli.handle_clipper')
    @patch('backend.cli.handle_upload')
    def test_orchestrate_project_pipeline(self, mock_handle_upload, mock_handle_clipper, mock_handle_metadata, mock_handle_highlights, mock_handle_transcribe):
        # We mock threading.Thread to run synchronously for the test
        with patch('threading.Thread') as mock_thread:
            def sync_start(target, args=(), kwargs={}):
                target(*args, **kwargs)
                return MagicMock()
            
            # Setup Thread mock to call target immediately when .start() is called
            mock_thread_instance = MagicMock()
            mock_thread.return_value = mock_thread_instance
            mock_thread.side_effect = lambda target, args=(), kwargs={}, daemon=None: MagicMock(start=lambda: target(*args, **kwargs))

            # Setup initial state
            (self.project_path / "transcription.txt").unlink(missing_ok=True)
            self.mock_metadata.highlights = []
            self.mock_metadata.video_metadata = {}
            self.mock_metadata.clips = []
            self.mock_metadata.uploaded = False
            
            # We will manually trigger the orchestration loop iterations
            # to avoid infinite loop and threading issues
            
            # 1. Transcribe eligible
            eligible = self.orchestrator._get_eligible_steps(self.project_id)
            self.assertEqual(eligible, ["transcribe"])
            
            for step in eligible:
                self.orchestrator._run_single_step(self.project_id, step)
            
            mock_handle_transcribe.assert_called_once()
            
            # Simulate completion
            (self.project_path / "transcription.txt").write_text("done") # Content for size > 0
            self.mock_metadata.transcription_file = "transcription.txt"
            
            # 2. Highlights and Metadata eligible
            eligible = self.orchestrator._get_eligible_steps(self.project_id)
            self.assertIn("highlights", eligible)
            self.assertIn("metadata", eligible)
            
            for step in eligible:
                self.orchestrator._run_single_step(self.project_id, step)
                
            mock_handle_highlights.assert_called_once()
            mock_handle_metadata.assert_called_once()
            
            # Simulate completion
            self.mock_metadata.highlights = [{"text": "h"}]
            self.mock_metadata.video_metadata = {"t": "t"}
            
            # 3. Clipper eligible
            eligible = self.orchestrator._get_eligible_steps(self.project_id)
            self.assertEqual(eligible, ["clipper"])
            
            for step in eligible:
                self.orchestrator._run_single_step(self.project_id, step)
                
            mock_handle_clipper.assert_called_once()
            
            # Simulate completion
            (self.project_path / "clips").mkdir(exist_ok=True)
            (self.project_path / "clips" / "c.mp4").touch()
            self.mock_metadata.clips = [{"filename": "c.mp4"}]
            
            # 4. Upload eligible
            eligible = self.orchestrator._get_eligible_steps(self.project_id)
            self.assertEqual(eligible, ["upload"])
            
            for step in eligible:
                self.orchestrator._run_single_step(self.project_id, step)
                
            mock_handle_upload.assert_called_once()

    def test_reset_project_pipeline(self):
        (self.project_path / "transcription.txt").write_text("test")
        (self.project_path / "word_map.csv").write_text("test")
        (self.project_path / "clips").mkdir(exist_ok=True)
        (self.project_path / "clips" / "clip_000.mp4").touch()

        metadata = self.mock_metadata
        metadata.highlights = [{"text": "test"}]
        metadata.video_metadata = {"title": "test"}
        metadata.transcription_file = "transcription.txt"
        metadata.components["word_map_file"] = "word_map.csv"

        self.orchestrator.reset_project_pipeline(self.project_id)

        self.assertFalse((self.project_path / "transcription.txt").exists())
        self.assertFalse((self.project_path / "word_map.csv").exists())
        self.assertFalse(any((self.project_path / "clips").iterdir()))

        updated_metadata = self.orchestrator.project_manager.save_project_metadata.call_args[0][1]
        self.assertEqual(updated_metadata.highlights, [])
        self.assertEqual(updated_metadata.video_metadata, {})
        self.assertEqual(updated_metadata.clips, [])
        self.assertIsNone(updated_metadata.clipper_start)
        self.assertIsNone(updated_metadata.clipper_end)
        self.assertIsNone(updated_metadata.transcription_file)
        self.assertNotIn("word_map_file", updated_metadata.components)
        self.assertNotIn("clips_dir", updated_metadata.components)

        self.orchestrator.active_project_orchestrators[self.project_id] = MagicMock()
        self.orchestrator.reset_project_pipeline(self.project_id)
        self.assertNotIn(self.project_id, self.orchestrator.active_project_orchestrators)

if __name__ == '__main__':
    unittest.main()
