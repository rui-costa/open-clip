import unittest
from io import BytesIO
from unittest.mock import MagicMock, patch, call
from backend.api import SimpleHandler
from http.server import BaseHTTPRequestHandler
from pathlib import Path
import json
import re

class TestSimpleHandler(unittest.TestCase):
    def setUp(self):
        self.mock_server = MagicMock()
        self.mock_socket = MagicMock()
        self.mock_socket.makefile.return_value = BytesIO(b"")
        
        # Patch the PipelineOrchestrator and ProjectManager at the module level
        self.patcher_orchestrator = patch('backend.api.pipeline_orchestrator')
        self.mock_orchestrator = self.patcher_orchestrator.start()
        
        self.patcher_project_manager = patch('backend.api.project_manager')
        self.mock_project_manager = self.patcher_project_manager.start()

        with patch('http.server.BaseHTTPRequestHandler.__init__', return_value=None):
            self.handler = SimpleHandler(self.mock_socket, ('127.0.0.1', 8000), self.mock_server)
            self.handler.wfile = BytesIO()
            self.handler.requestline = "GET / HTTP/1.1"
            self.handler.request_version = "HTTP/1.1"
            self.handler.client_address = ('127.0.0.1', 8000)

    def tearDown(self):
        self.patcher_orchestrator.stop()
        self.patcher_project_manager.stop()

    def simulate_request(self, method, path, headers, body=b""):
        self.handler.command = method
        self.handler.path = path
        self.handler.headers = headers
        self.handler.rfile = BytesIO(body)
        self.handler.requestline = f"{method} {path} HTTP/1.1"
        self.handler.client_address = ('127.0.0.1', 8000)
        
        if method == 'GET':
            self.handler.do_GET()
        elif method == 'POST':
            self.handler.do_POST()
        elif method == 'DELETE':
            self.handler.do_DELETE()
        elif method == 'OPTIONS':
            self.handler.do_OPTIONS()

    def test_do_options_cors(self):
        self.simulate_request('OPTIONS', '/project/create', {})
        response = self.handler.wfile.getvalue().decode()
        self.assertIn('Access-Control-Allow-Headers: Content-Type, X-File-Name', response)

    def test_create_project_raw_upload(self):
        self.mock_project_manager.create_project.return_value = MagicMock(name="test-project-id")
        self.mock_project_manager.create_project.return_value.name = "test-project-id"
        
        headers = {'Content-Length': '5', 'X-File-Name': 'test.mp4'}
        body = b"12345"
        self.simulate_request('POST', '/project/create', headers, body)
        response = self.handler.wfile.getvalue().decode()
        self.assertIn('"project_id": "test-project-id"', response)
        self.mock_project_manager.create_project.assert_called_once() # Ensure it's called

    def test_send_cors_error(self):
        self.handler.send_cors_error(400, "Bad Request")
        response = self.handler.wfile.getvalue().decode()
        self.assertIn('Access-Control-Allow-Origin: *', response)
        self.assertIn('"error": "Bad Request"', response)

    def test_post_project_step_start_all(self):
        project_id = "test_project_id"
        request_body = json.dumps({"project_id": project_id, "step": "all", "action": "START"}).encode()
        headers = {'Content-Length': str(len(request_body)), 'Content-Type': 'application/json'}
        self.simulate_request('POST', '/project/step', headers, request_body)
        self.mock_orchestrator.start_project_pipeline.assert_called_once_with(project_id)
        response = self.handler.wfile.getvalue().decode()
        self.assertIn('"status": "pipeline_started"', response)

    def test_post_project_step_stop_all(self):
        project_id = "test_project_id"
        request_body = json.dumps({"project_id": project_id, "step": "all", "action": "STOP"}).encode()
        headers = {'Content-Length': str(len(request_body)), 'Content-Type': 'application/json'}
        self.simulate_request('POST', '/project/step', headers, request_body)
        self.mock_orchestrator.stop_project_pipeline.assert_called_once_with(project_id)
        response = self.handler.wfile.getvalue().decode()
        self.assertIn('"status": "pipeline_stopped"', response)

    def test_post_project_step_start_single_step(self):
        project_id = "test_project_id"
        # Mock pipeline_config and is_step_complete for single step logic
        self.mock_orchestrator.pipeline_config = {
            "steps": {"transcribe": {"command": "transcribe", "depends_on": []}}
        }
        self.mock_orchestrator.is_step_complete.return_value = True # No dependencies
        self.mock_orchestrator.active_processes = {} # Not running

        request_body = json.dumps({"project_id": project_id, "step": "transcribe", "action": "START"}).encode()
        headers = {'Content-Length': str(len(request_body)), 'Content-Type': 'application/json'}
        
        with patch.object(self.mock_orchestrator, '_run_single_step') as mock_run_single_step:
            self.simulate_request('POST', '/project/step', headers, request_body)
            mock_run_single_step.assert_called_once_with(project_id, "transcribe")
        response = self.handler.wfile.getvalue().decode()
        self.assertIn('"status": "started"', response)

    def test_post_project_step_start_single_step_dependencies_not_met(self):
        project_id = "test_project_id"
        self.mock_orchestrator.pipeline_config = {
            "steps": {"highlights": {"command": "highlights", "depends_on": ["transcribe"]}}
        }
        self.mock_orchestrator.is_step_complete.side_effect = lambda pid, step: False if step == "transcribe" else True

        request_body = json.dumps({"project_id": project_id, "step": "highlights", "action": "START"}).encode()
        headers = {'Content-Length': str(len(request_body)), 'Content-Type': 'application/json'}
        self.simulate_request('POST', '/project/step', headers, request_body)
        response = self.handler.wfile.getvalue().decode()
        self.assertIn('"status": "dependencies_not_met"', response)
        self.assertIn('"missing": "transcribe"', response)
        self.mock_orchestrator._run_single_step.assert_not_called()

    def test_post_project_step_stop_single_step(self):
        project_id = "test_project_id"
        # Mock a running process
        mock_proc = MagicMock()
        self.mock_orchestrator.active_processes = {f"{project_id}_transcribe": mock_proc}
        self.mock_orchestrator.pipeline_config = {
            "steps": {"transcribe": {"command": "transcribe", "depends_on": []}}
        }

        request_body = json.dumps({"project_id": project_id, "step": "transcribe", "action": "STOP"}).encode()
        headers = {'Content-Length': str(len(request_body)), 'Content-Type': 'application/json'}
        self.simulate_request('POST', '/project/step', headers, request_body)
        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called_once_with(timeout=5)
        self.assertNotIn(f"{project_id}_transcribe", self.mock_orchestrator.active_processes)
        response = self.handler.wfile.getvalue().decode()
        self.assertIn('"status": "stopped"', response)

    def test_delete_project_stops_orchestrator(self):
        project_id = "test_project_id"
        self.mock_project_manager.delete_project.return_value = True
        self.simulate_request('DELETE', f'/project/{project_id}', {})
        self.mock_project_manager.delete_project.assert_called_once_with(project_id)
        self.mock_orchestrator.stop_project_pipeline.assert_called_once_with(project_id)
        response = self.handler.wfile.getvalue().decode()
        self.assertIn('"status": "deleted"', response)

    def test_get_pipeline_config(self):
        mock_config = {"steps": {"test": {}}}
        self.mock_orchestrator.pipeline_config = mock_config
        self.simulate_request('GET', '/pipeline/config', {})
        response = self.handler.wfile.getvalue().decode()
        self.assertEqual(json.loads(re.search(r'\r\n\r\n(.*)', response, re.DOTALL).group(1)), mock_config)
        
    def test_get_active_processes(self):
        self.mock_orchestrator.active_processes = {"proj1_stepA": MagicMock(), "proj2_stepB": MagicMock()}
        self.simulate_request('GET', '/active_processes', {})
        response = self.handler.wfile.getvalue().decode()
        self.assertEqual(json.loads(re.search(r'\r\n\r\n(.*)', response, re.DOTALL).group(1)), ["proj1_stepA", "proj2_stepB"])

        project_id = "test_project_id"
        self.mock_project_manager.delete_project.return_value = True
        self.handler.command = 'DELETE'
        self.handler.path = f'/project/{project_id}'
        self.handler.do_DELETE()
        self.mock_project_manager.delete_project.assert_called_once_with(project_id)
