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
            asyncio.run(service.execute(project))

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

        import concurrent.futures

        def pipeline_runner():
            steps = self.pipeline_config['steps']
            completed_steps = set()
            lock = threading.Lock()

            def run_step_task(step_name):
                # Pass the existing project instance to avoid concurrent load conflicts
                self._exec_service(project, step_name)
                with lock:
                    completed_steps.add(step_name)

            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = {}
                while len(completed_steps) < len(steps):
                    for step_name, config in steps.items():
                        if step_name not in futures and step_name not in completed_steps:
                            dependencies = config.get('depends_on', [])
                            if all(dep in completed_steps for dep in dependencies):
                                futures[step_name] = executor.submit(run_step_task, step_name)
                    
                    time.sleep(0.1) # Avoid tight loop

        thread = threading.Thread(target=pipeline_runner)
        with self._lock:
            self.active_project_orchestrators[project_id] = thread
        thread.start()
