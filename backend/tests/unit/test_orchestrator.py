import unittest
from unittest.mock import MagicMock, patch
from backend.src.orchestrator import PipelineOrchestrator

class TestPipelineOrchestrator(unittest.TestCase):
    def setUp(self):
        # Patch _load_pipeline_config to avoid disk access during init
        with patch.object(PipelineOrchestrator, '_load_pipeline_config') as mock_load:
            mock_load.return_value = {
                "execution_order": ["transcribe", "metadata", "highlights", "clipper", "upload"],
                "steps": {
                    "transcribe": {"command": "transcribe", "depends_on": [], "auto_run": True},
                    "metadata": {"command": "metadata", "depends_on": ["transcribe"], "auto_run": True},
                    "highlights": {"command": "highlights", "depends_on": ["transcribe"], "auto_run": True},
                    "clipper": {"command": "clipper", "depends_on": ["highlights", "metadata"], "auto_run": True},
                    "upload": {"command": "upload", "depends_on": ["clipper"], "auto_run": False}
                }
            }
            self.orchestrator = PipelineOrchestrator(projects_base_dir="projects", config_path="pipeline.json")
            
        self.orchestrator.project_manager = MagicMock()
        self.project_id = "test_project"

    def test_get_eligible_steps_initial(self):
        with patch.object(self.orchestrator, 'is_step_complete', return_value=False):
            steps = self.orchestrator._get_eligible_steps(self.project_id)
            self.assertEqual(steps, ["transcribe"])

    def test_get_eligible_steps_after_transcribe(self):
        with patch.object(self.orchestrator, 'is_step_complete', side_effect=lambda pid, step: step == "transcribe"):
            steps = self.orchestrator._get_eligible_steps(self.project_id)
            self.assertIn("metadata", steps)
            self.assertIn("highlights", steps)

    def test_run_single_step_updates_status(self):
        with patch("subprocess.Popen") as mock_popen:
            mock_popen.return_value.returncode = 0
            
            self.orchestrator._run_single_step(self.project_id, "metadata")
            
            self.orchestrator.project_manager.update_step_status.assert_called_with(
                self.project_id, "metadata", status="completed"
            )

if __name__ == '__main__':
    unittest.main()
