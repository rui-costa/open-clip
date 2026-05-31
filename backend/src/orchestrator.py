import json
import logging
import threading
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from backend.src.dataclasses.data import Project

from backend.src.services.transcriber import Transcriber
from backend.src.services.llm_query import LLMQuery
from backend.src.services.clipper import Clipper
from backend.src.services.uploader import Uploader

logger = logging.getLogger(__name__)

class PipelineOrchestrator:
    def __init__(self, config_path: str = "backend/config/pipeline.json", active_processes: Dict[str, Any] = None, services: Dict[str, Any] = None):
        self.config_path = Path(config_path)
        self.pipeline_config = self._load_pipeline_config()
        self.active_project_orchestrators: Dict[str, threading.Thread] = {}
        self.active_processes = active_processes if active_processes is not None else {}
        self._lock = threading.Lock()
        
        # Injectable services
        self.services = services or {
            "transcription": Transcriber(),
            "highlights": LLMQuery(task_name="extract_highlights"),
            "metadata": LLMQuery(task_name="generate_metadata"),
            "clipper": Clipper(),
            "upload": Uploader()
        }

    def _load_pipeline_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Pipeline config not found at {self.config_path}")
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def _exec_service(self, project: Project, step_name: str):
        """Helper to run service execution synchronously within a thread."""
        service = self.services.get(step_name)
        if service:
            import asyncio
            import inspect
            if inspect.iscoroutinefunction(service.execute):
                asyncio.run(service.execute(project))
            else:
                service.execute(project)
            
            if project.step_statuses.get(step_name) == "error":
                raise RuntimeError(f"Service {step_name} failed.")

    def run_step(self, project_id: str, step_name: str):
        """Triggers a step in the background."""
        project = Project(project_id)
        thread = threading.Thread(target=self._exec_service, args=(project, step_name))
        with self._lock:
            self.active_project_orchestrators[project_id] = thread
        thread.start()

    def run_pipeline(self, project_id: str):
        """Triggers the full pipeline in the background using dependency graph."""
        project = Project(project_id)
        # Global reset: each service resets only its own state
        for service in self.services.values():
            if hasattr(service, 'reset_metadata'):
                service.reset_metadata(project)

        def pipeline_runner():
            steps = self.pipeline_config['steps']
            while True:
                project.load(project.project_id)

                # Check for failure in pipeline
                if any(project.step_statuses.get(s) == "error" for s in steps):
                    break

                # Check if pipeline finished
                if all(project.step_statuses.get(s) == "completed" for s in steps):
                    break

                for step_name, config in steps.items():
                    # Only trigger if status is not started
                    if project.step_statuses.get(step_name) not in [None, "todo", "pending"]:
                        continue

                    # Strict dependency check
                    dependencies = config.get('depends_on', [])
                    if all(project.step_statuses.get(dep) == "completed" for dep in dependencies):
                        # Only trigger auto-run
                        if config.get('auto_run', True):
                            self.run_step(project.project_id, step_name)

                time.sleep(1.0)

        thread = threading.Thread(target=pipeline_runner)
        with self._lock:
            self.active_project_orchestrators[project_id] = thread
        thread.start()
