import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import json
import os
import time

from backend.src.orchestrator import PipelineOrchestrator
from backend.src.manager import ProjectRepository
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
        self.orchestrator.project_repo = MagicMock(spec=ProjectRepository)
        self.orchestrator.project_repo.get_project_path.return_value = str(self.project_path)
        
        # We need a partial mock for the repository to get existing data, 
        # but the orchestrator now uses repo.get_project(id)
        self.orchestrator.project_repo.get_project.return_value = self.mock_metadata

    def tearDown(self):
        import shutil
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_is_step_complete(self):
        # Setup: Project starts with empty status
        self.mock_metadata.step_statuses = {}
        self.orchestrator.project_repo.get_project.return_value = self.mock_metadata
        
        self.assertFalse(self.orchestrator.is_step_complete(self.project_id, "transcribe"))
        
        # Action: Set status to completed
        self.mock_metadata.step_statuses["transcribe"] = "completed"
        self.assertTrue(self.orchestrator.is_step_complete(self.project_id, "transcribe"))

    def test_get_eligible_steps(self):
        # Setup: Project starts with empty status
        self.mock_metadata.step_statuses = {}
        self.orchestrator.project_repo.get_project.return_value = self.mock_metadata
        
        eligible = self.orchestrator._get_eligible_steps(self.project_id)
        self.assertIn("transcribe", eligible)
        
        # Action: Complete transcribe
        self.mock_metadata.step_statuses["transcribe"] = "completed"
        eligible = self.orchestrator._get_eligible_steps(self.project_id)
        self.assertIn("highlights", eligible)
        self.assertIn("metadata", eligible)

    def test_run_single_step_updates_status(self):
        mock_service = MagicMock()
        
        # Inject mocked services
        self.orchestrator.services = {
            "transcribe": MagicMock(),
            "highlights": MagicMock(),
            "metadata": mock_service,
            "clipper": MagicMock(),
            "upload": MagicMock()
        }

        # Mock the repo to return our project object
        from backend.src.project import Project
        mock_project = MagicMock(spec=Project)
        mock_project.project_id = self.project_id
        
        self.orchestrator.project_repo.get_project.return_value = mock_project

        self.orchestrator._run_single_step(self.project_id, "metadata")
        
        # Verify save_project was called
        self.orchestrator.project_repo.save_project.assert_called_once_with(mock_project)

    def test_orchestrate_project_pipeline_simple(self):
        self.mock_metadata.highlights = [{"text": "h"}]
        self.mock_metadata.video_metadata = {"t": "t"}
        self.mock_metadata.transcription_file = "transcription.txt"
        
        eligible = self.orchestrator._get_eligible_steps(self.project_id)
        self.assertIn("transcribe", eligible)

    def test_pipeline_advances_after_step_completion(self):
        # Setup: Project has completed transcribe status
        self.mock_metadata.step_statuses = {"transcribe": "completed"}
        self.orchestrator.project_repo.get_project.return_value = self.mock_metadata

        with patch.dict('sys.modules', {
            'backend.src.transcriber': MagicMock(),
            'backend.src.llm_executor': MagicMock(),
        }):
            self.assertTrue(self.orchestrator.is_step_complete(self.project_id, "transcribe"))
            eligible = self.orchestrator._get_eligible_steps(self.project_id)
            self.assertIn("highlights", eligible)
if __name__ == '__main__':
    unittest.main()
