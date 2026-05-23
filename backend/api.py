import json
import logging
import subprocess
import tempfile
import os
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import threading
from dataclasses import asdict

from backend.src.manager import ProjectManager
from backend.src.exceptions import ProjectNotFoundError
from backend.src.orchestrator import PipelineOrchestrator
from backend.src.settings_manager import settings_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Track active subprocesses (shared state)
active_processes = {}

# Initialize ProjectManager and PipelineOrchestrator
project_manager = ProjectManager()
pipeline_orchestrator = PipelineOrchestrator(active_processes=active_processes)

class SimpleHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-File-Name')
        self.end_headers()

    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')
        elif self.path == '/active_processes':
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(list(pipeline_orchestrator.active_processes.keys())).encode())
        elif self.path == '/pipeline/config':
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(pipeline_orchestrator.pipeline_config).encode())
        elif self.path == '/settings':
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            settings = settings_manager.get_all()
            payload = {
                "settings": settings,
                "pipeline_config": pipeline_orchestrator.pipeline_config
            }
            self.wfile.write(json.dumps(payload).encode())
        elif self.path == '/projects':
            all_projects_metadata = []
            project_ids = project_manager.list_projects()
            for project_id in project_ids:
                try:
                    metadata = project_manager.get_metadata(project_id)
                    meta_dict = asdict(metadata)
                    meta_dict['created_at'] = metadata.created_at.isoformat()
                    all_projects_metadata.append(meta_dict)
                except ProjectNotFoundError:
                    logger.warning(f"Project metadata not found for ID: {project_id}. Skipping.")
                    continue
            all_projects_metadata.sort(key=lambda x: x['created_at'], reverse=True)
            self.send_response(200)
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(all_projects_metadata).encode())
        elif self.path.startswith('/projects/static/'):
            parts = self.path.split('/')
            if len(parts) < 4:
                self.send_error(400)
                return
            project_id = parts[3]
            relative_path = '/'.join(parts[4:])
            try:
                project_path = project_manager.get_project_path(project_id)
                file_path = project_path / relative_path
                # Validate the final file path to prevent traversal via relative_path
                project_manager._validate_path(file_path)

                if file_path.exists() and file_path.is_file():
                    if file_path.suffix == '.mp4': mime_type = 'video/mp4'
                    elif file_path.suffix == '.json': mime_type = 'application/json'
                    else: mime_type = 'application/octet-stream'
                    file_size = file_path.stat().st_size
                    range_header = self.headers.get('Range')
                    if range_header and mime_type == 'video/mp4':
                        try:
                            range_val = range_header.replace('bytes=', '').split('-')
                            start = int(range_val[0])
                            end = int(range_val[1]) if range_val[1] else file_size - 1
                            if start >= file_size or end >= file_size:
                                self.send_error(416, "Requested Range Not Satisfiable")
                                return
                            content_length = end - start + 1
                            self.send_response(206)
                            self.send_header('Access-Control-Allow-Origin', '*')
                            self.send_header('Content-type', mime_type)
                            self.send_header('Accept-Ranges', 'bytes')
                            self.send_header('Content-Range', f'bytes {start}-{end}/{file_size}')
                            self.send_header('Content-Length', str(content_length))
                            self.end_headers()
                            with open(file_path, 'rb') as f:
                                f.seek(start)
                                bytes_sent = 0
                                while bytes_sent < content_length:
                                    chunk = f.read(min(65536, content_length - bytes_sent))
                                    if not chunk: break
                                    try:
                                        self.wfile.write(chunk)
                                        bytes_sent += len(chunk)
                                    except (BrokenPipeError, ConnectionResetError): return
                            return
                        except (ValueError, IndexError): pass
                    self.send_response(200)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Content-type', mime_type)
                    self.send_header('Content-Length', str(file_size))
                    self.send_header('Accept-Ranges', 'bytes')
                    self.end_headers()
                    with open(file_path, 'rb') as f:
                        try: self.wfile.write(f.read())
                        except (BrokenPipeError, ConnectionResetError): return
                else:
                    self.send_error(404)
            except PermissionError as e:
                self.send_error(403, str(e))
            except Exception as e:
                self.send_error(500, str(e))
        elif self.path.startswith('/project/') and '/clip/' in self.path and self.path.endswith('/upload'):
            parts = self.path.split('/')
            project_id = parts[2]
            clip_id = parts[4]
            try:
                metadata = project_manager.get_metadata(project_id)
                clip_idx = int(clip_id)
                clip_filename = f"clip_{clip_idx:03d}.mp4"
                clip_path = project_manager.get_clip_video_path(project_id, clip_filename)
                from backend.src.uploader import YoutubeUploader
                with open("backend/youtube_credentials/client_secrets.json", "r") as f:
                    client_secrets = json.load(f)
                uploader = YoutubeUploader("backend/youtube_credentials", client_secrets)
                clip_text = metadata.highlights[clip_idx].get("text", "AI Generated Clip")
                result = uploader.upload_video(
                    file_path=clip_path,
                    title=clip_text[:90],
                    description=f"Generated from project {metadata.name}"
                )
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "video_url": result["url"]}).encode())
            except Exception as e:
                logger.error(f"Error uploading clip: {e}")
                self.send_cors_error(500, f"Upload failed: {str(e)}")
        elif self.path.startswith('/project/'):
            project_id = self.path.split('/')[-1]
            project_path = Path("projects") / project_id
            metadata_file = project_path / "metadata.json"
            if metadata_file.exists():
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                with open(metadata_file, 'r') as f:
                    self.wfile.write(f.read().encode())
            else:
                self.send_error(404)
        else:
            self.send_error(404)

    def do_DELETE(self):
        if self.path.startswith('/project/'):
            project_id = self.path.split('/')[-1]
            try:
                if project_manager.delete_project(project_id):
                    pipeline_orchestrator.stop_project_pipeline(project_id)
                    self.send_response(200)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "deleted"}).encode())
                else:
                    self.send_error(404, "Project not found")
            except PermissionError as e:
                self.send_error(403, str(e))
            except Exception as e:
                self.send_cors_error(500, f"Internal Server Error: {str(e)}")
        else:
            self.send_error(404)

    def send_cors_error(self, code, message):
        self.send_response(code)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode())

    def do_POST(self):
        if self.path == '/project/create':
            try:
                filename = self.headers.get('X-File-Name')
                if not filename:
                    self.send_cors_error(400, "Missing 'X-File-Name' header")
                    return
                content_length = int(self.headers.get('Content-Length', 0))
                fd, temp_path = tempfile.mkstemp(suffix=os.path.splitext(filename)[1])
                try:
                    with os.fdopen(fd, 'wb') as temp_file:
                        remaining = content_length
                        while remaining > 0:
                            chunk_size = min(remaining, 65536)
                            data_chunk = self.rfile.read(chunk_size)
                            if not data_chunk: break
                            temp_file.write(data_chunk)
                            remaining -= len(data_chunk)
                    temp_dir = os.path.dirname(temp_path)
                    final_temp_path = os.path.join(temp_dir, filename)
                    if os.path.exists(final_temp_path):
                        final_temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}_{filename}")
                    os.rename(temp_path, final_temp_path)
                    project_path = project_manager.create_project(file_path=final_temp_path)
                    project_id = project_path.name
                    os.remove(final_temp_path)
                    self.send_response(200)
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"project_id": project_id}).encode())
                except Exception as e:
                    if os.path.exists(temp_path): os.remove(temp_path)
                    elif 'final_temp_path' in locals() and os.path.exists(final_temp_path): os.remove(final_temp_path)
                    raise e
            except Exception as e:
                logger.error(f"Error during project creation: {e}")
                self.send_cors_error(500, f"Internal Server Error: {str(e)}")
                return
        content_length = int(self.headers.get('Content-Length', 0))
        try:
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.send_cors_error(400, "Invalid JSON body")
            return
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        if self.path == '/settings':
            try:
                settings_data = data.get('settings', {})
                pipeline_config = data.get('pipeline_config', None)
                if settings_data: settings_manager.update_batch(settings_data)
                if pipeline_config:
                    with open(pipeline_orchestrator.config_path, 'w') as f:
                        json.dump(pipeline_config, f, indent=2)
                    pipeline_orchestrator.reload_config()
                self.wfile.write(json.dumps({"status": "settings_updated"}).encode())
            except Exception as e:
                logger.error(f"Error updating settings: {e}")
                self.send_cors_error(500, f"Internal Server Error: {str(e)}")
                return
        elif self.path == '/project/step':
            project_id = data['project_id']
            step = data['step']
            action = data['action']
            if step == 'all':
                if action == 'START':
                    pipeline_orchestrator.reset_project_pipeline(project_id)
                    pipeline_orchestrator.start_project_pipeline(project_id)
                    self.wfile.write(json.dumps({"status": "pipeline_started"}).encode())
                elif action == 'STOP':
                    pipeline_orchestrator.stop_project_pipeline(project_id)
                    self.wfile.write(json.dumps({"status": "pipeline_stopped"}).encode())
                return
            step_config = pipeline_orchestrator.pipeline_config['steps'].get(step)
            if not step_config:
                self.send_cors_error(404, f"Step {step} not found in pipeline config")
                return
            key = f"{project_id}_{step}"
            if action == 'START':
                dependencies = step_config.get('depends_on', [])
                for dep in dependencies:
                    if not pipeline_orchestrator.is_step_complete(project_id, dep):
                        self.wfile.write(json.dumps({"status": "dependencies_not_met", "missing": dep}).encode())
                        return
                if key in pipeline_orchestrator.active_processes:
                    self.wfile.write(json.dumps({"status": "already_running"}).encode())
                    return
                threading.Thread(target=pipeline_orchestrator._run_single_step, args=(project_id, step)).start()
                self.wfile.write(json.dumps({"status": "started"}).encode())
            elif action == 'STOP':
                if key in pipeline_orchestrator.active_processes:
                    proc = pipeline_orchestrator.active_processes[key]
                    proc.terminate()
                    proc.wait(timeout=5)
                    del pipeline_orchestrator.active_processes[key]
                    self.wfile.write(json.dumps({"status": "stopped"}).encode())
                else:
                    self.send_cors_error(400, "Not running")
        else:
            self.send_error(404)

def run():
    httpd = HTTPServer(('', 8000), SimpleHandler)
    logger.info("Server started on port 8000")
    httpd.serve_forever()

if __name__ == '__main__':
    run()
