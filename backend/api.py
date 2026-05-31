import json
import logging
import uuid
import os
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from dataclasses import asdict

from backend.src.dataclasses.data import Project
from backend.src.registry import list_projects, delete_project
from backend.src.orchestrator import PipelineOrchestrator
from backend.src.settings_manager import settings_manager

# Generate a unique session ID for this run
SESSION_ID = str(uuid.uuid4())[:8]

# Logging configuration with persistence
log_level_map = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}

class SessionFilter(logging.Filter):
    def filter(self, record):
        record.session_id = SESSION_ID
        return True

def setup_logging():
    level_name = settings_manager.get("log_level", "INFO").upper()
    level = log_level_map.get(level_name, logging.INFO)
    
    # Filename format: YYYYMMDD_HHMMSS.log
    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"{timestamp_str}.log"
    log_file = Path("backend/logs") / log_filename
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    formatter = logging.Formatter('%(asctime)s - [%(session_id)s] - %(name)s - %(levelname)s - %(message)s')
    
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)
    file_handler.addFilter(SessionFilter())
    
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(SessionFilter())
    
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)
    
    # Force level on all existing loggers
    for logger_name in logging.root.manager.loggerDict:
        logging.getLogger(logger_name).setLevel(level)
    
    # Verification
    root_logger.info(f"Logging initialized with level={logging.getLevelName(level)}")

setup_logging()
logger = logging.getLogger(__name__)

# Track active subprocesses (shared state)
active_processes = {}

# Initialize PipelineOrchestrator
pipeline_orchestrator = PipelineOrchestrator(active_processes=active_processes)

class SimpleHandler(BaseHTTPRequestHandler):
    def send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-File-Name')

    def send_json_response(self, data, code=200):
        self.send_response(code)
        self.send_cors_headers()
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        try:
            self.wfile.write(json.dumps(data).encode())
        except (BrokenPipeError, ConnectionResetError):
            logger.warning("Client disconnected before response could be sent")

    def send_cors_error(self, code, message):
        self.send_json_response({"error": message}, code)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    # GET Handlers
    def handle_get_health(self): self.send_json_response({"status": "ok"})
    def handle_get_processes(self): self.send_json_response(list(pipeline_orchestrator.active_processes.keys()))
    def handle_get_config(self): self.send_json_response(pipeline_orchestrator.pipeline_config)
    def handle_get_settings(self):
        self.send_json_response({
            "settings": settings_manager.get_all(),
            "pipeline_config": pipeline_orchestrator.pipeline_config
        })

    def handle_get_projects(self):
        all_projects = []
        for project_id in list_projects():
            try:
                project = Project(project_id)
                all_projects.append(project.to_dict())
            except Exception as e:
                logger.error(f"Failed to load project {project_id}: {e}")
        all_projects.sort(key=lambda x: x['created_at'], reverse=True)
        self.send_json_response(all_projects)

    def handle_get_project_file(self):
        parts = self.path.split('/')
        project_id = parts[3]
        rel_path = '/'.join(parts[4:])
        try:
            project = Project(project_id)
            if rel_path.startswith('clips/'):
                file_path = Path(project.get_clip_path(rel_path.split('/')[-1]))
            else:
                file_path = Path(project.base_directory) / project_id / rel_path

            if file_path.exists() and file_path.is_file():
                mime = 'video/mp4' if file_path.suffix == '.mp4' else 'application/octet-stream'
                self.send_response(200)
                self.send_cors_headers()
                self.send_header('Content-type', mime)
                self.send_header('Content-Length', str(file_path.stat().st_size))
                self.end_headers()
                with open(file_path, 'rb') as f:
                    try:
                        while True:
                            chunk = f.read(65536)
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                    except (BrokenPipeError, ConnectionResetError):
                        logger.warning("Client disconnected during file transfer")
            else:
                self.send_error(404)
        except Exception as e:
            self.send_error(500, str(e))

    def handle_get_project_detail(self):
        project_id = self.path.split('/')[-1]
        try:
            self.send_json_response(Project(project_id).to_dict())
        except Exception:
            self.send_cors_error(404, "Project not found")

    def handle_get_execution_status(self):
        project_id = self.path.split('/')[2]
        project = Project(project_id)
        
        # Merge file statuses with active processes
        statuses = project.step_statuses.copy()
        for k in pipeline_orchestrator.active_processes:
            if k.startswith(project_id):
                step_name = k.split('_')[-1]
                statuses[step_name] = "running"
            
        # Check dependencies for locked steps
        pipeline_config = pipeline_orchestrator.pipeline_config
        for step_name, config in pipeline_config['steps'].items():
            if step_name not in statuses or statuses[step_name] == "todo":
                dependencies = config.get('depends_on', [])
                all_deps_met = all(statuses.get(dep) == "completed" for dep in dependencies)
                statuses[step_name] = "locked" if not all_deps_met else "todo"
                    
        self.send_json_response(statuses)

    def do_GET(self):
        if self.path == '/health': self.handle_get_health()
        elif self.path == '/active_processes': self.handle_get_processes()
        elif self.path == '/pipeline/config': self.handle_get_config()
        elif self.path == '/settings': self.handle_get_settings()
        elif self.path == '/projects': self.handle_get_projects()
        elif self.path.startswith('/projects/static/'): self.handle_get_project_file()
        elif self.path.startswith('/project/') and self.path.endswith('/execution_status'):
            self.handle_get_execution_status()
        elif self.path.startswith('/project/'):
            self.handle_get_project_detail()
        else: self.send_error(404)

    # POST Handlers
    def handle_post_init(self):
        project = Project()
        self.send_json_response({"project_id": project.project_id})

    def handle_post_upload(self):
        project_id = self.path.split('/')[-1]
        project = Project(project_id)
        content_length = int(self.headers.get('Content-Length', 0))
        new_filename = f"original{Path(project.name).suffix or '.mp4'}"
        project_dir = Path(project.base_directory) / project_id
        project_dir.mkdir(parents=True, exist_ok=True)
        file_path = project_dir / new_filename
        
        with open(file_path, 'wb') as f:
            remaining = content_length
            while remaining > 0:
                chunk = self.rfile.read(min(remaining, 65536))
                if not chunk: break
                f.write(chunk)
                remaining -= len(chunk)

        self.send_json_response({"status": "uploaded", "path": str(file_path)})
    def handle_post_step(self):
        content_length = int(self.headers.get('Content-Length', 0))
        data = json.loads(self.rfile.read(content_length))
        project_id, step, action = data['project_id'], data['step'], data['action']
        
        if step == 'all' and action == 'START':
            pipeline_orchestrator.run_pipeline(project_id)
        elif action == 'START':
            pipeline_orchestrator.run_step(project_id, step)
        
        self.send_json_response({"status": "started"})

    def handle_post_upload_clip(self):
        parts = self.path.split('/')
        project_id, clip_id = parts[2], int(parts[4])
        try:
            result = pipeline_orchestrator.upload_clip(project_id, clip_id)
            self.send_json_response({"status": "success", "video_url": result["url"]})
        except Exception as e:
            self.send_cors_error(500, f"Upload failed: {str(e)}")

    def do_POST(self):
        if self.path == '/project/init': self.handle_post_init()
        elif self.path.startswith('/project/upload/'): self.handle_post_upload()
        elif self.path == '/project/step': self.handle_post_step()
        elif self.path.endswith('/upload'): self.handle_post_upload_clip()
        elif self.path == '/settings/log_level':
             content_length = int(self.headers.get('Content-Length', 0))
             data = json.loads(self.rfile.read(content_length))
             new_level = data.get("log_level").upper()
             if new_level in log_level_map:
                 settings_manager.set("log_level", new_level)
                 # Update current logger and all child loggers
                 new_level_const = log_level_map[new_level]
                 logging.getLogger().setLevel(new_level_const)
                 for logger_name in logging.root.manager.loggerDict:
                     logging.getLogger(logger_name).setLevel(new_level_const)
                 self.send_json_response({"status": "success"})
             else:
                 self.send_cors_error(400, "Invalid log level")
        else: self.send_error(404)

    # DELETE Handlers
    def do_DELETE(self):
        if self.path.startswith('/project/'):
            project_id = self.path.split('/')[-1]
            if delete_project(project_id):
                self.send_json_response({"status": "deleted"})
            else:
                self.send_error(404, "Project not found")
        else:
            self.send_error(404)

def run():
    httpd = ThreadingHTTPServer(('', 8000), SimpleHandler)
    logger.info(f"Server started on port 8000, session={SESSION_ID}")
    httpd.serve_forever()

if __name__ == '__main__':
    run()
