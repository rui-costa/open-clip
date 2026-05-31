import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from backend.src.orchestrator import PipelineOrchestrator
from backend.src.dataclasses.data import Project

class TestPipelineOrchestrator(unittest.TestCase):
    def setUp(self):
        self.config_path = Path("backend/config/pipeline.json")
        self.orchestrator = PipelineOrchestrator(config_path=str(self.config_path))
        self.project_id = "test_project"

    @patch('backend.src.dataclasses.data.Project.load')
    def test_run_single_step(self, mock_load):
        mock_project = MagicMock(spec=Project)
        mock_load.return_value = mock_project
        
        mock_service = MagicMock()
        # Mocking an async execute method
        mock_service.execute = unittest.mock.AsyncMock()
        self.orchestrator.services = {"metadata": mock_service}

        import asyncio
        asyncio.run(self.orchestrator.run_step(self.project_id, "metadata"))
        
        mock_service.execute.assert_called_once_with(mock_project)

if __name__ == '__main__':
    unittest.main()
