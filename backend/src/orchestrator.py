import json
import logging
import threading
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from backend.src.manager import ProjectRepository
from backend.src.project import Project

from backend.src.services.transcriber import Transcriber
from backend.src.services.llm_query import LLMQuery
from backend.src.services.clipper import Clipper

logger = logging.getLogger(__name__)

class PipelineOrchestrator:
    def __init__(self, config_path: str = "backend/config/pipeline.json", active_processes: Dict[str, Any] = None, services: Dict[str, Any] = None):
        self.project_repo = ProjectRepository()
        self.config_path = Path(config_path)
        self.pipeline_config = self._load_pipeline_config()
        self.active_project_orchestrators: Dict[str, threading.Thread] = {}
        self.active_processes = active_processes if active_processes is not None else {}
        self._lock = threading.Lock()
        
        # Injectable services
        self.services = services or {
            "transcribe": Transcriber(),
            "highlights": LLMQuery(task_name="extract_highlights"),
            "metadata": LLMQuery(task_name="generate_metadata"),
            "clipper": Clipper()
        }

    def _load_pipeline_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Pipeline config not found at {self.config_path}")
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def reload_config(self):
        logger.info("Reloading pipeline configuration...")
        self.pipeline_config = self._load_pipeline_config()

    def is_step_complete(self, project_id: str, step_name: str) -> bool:
        project = self.project_repo.get_project(project_id)
        return project.step_statuses.get(step_name) == "completed"
    
    def _get_eligible_steps(self, project_id: str) -> List[str]:
        eligible_steps = []
        for step_name in self.pipeline_config['execution_order']:
            step_config = self.pipeline_config['steps'].get(step_name)
            if not step_config:
                continue
            if not step_config.get('auto_run', True):
                continue
            if self.is_step_complete(project_id, step_name):
                continue
            
            # Check if already running (thread-safe check)
            with self._lock:
                if f"{project_id}_{step_name}" in self.active_processes:
                    continue

            dependencies = step_config.get('depends_on', [])
            all_deps_complete = all(self.is_step_complete(project_id, dep) for dep in dependencies)

            if all_deps_complete:
                eligible_steps.append(step_name)
        return eligible_steps

    def run_step(self, project_id: str, step_name: str):
        project = self.project_repo.get_project(project_id)
        service = self.services.get(step_name)
        
        if not service:
            logger.error(f"No service instance found for step: {step_name}")
            return

        logger.info(f"Starting step '{step_name}' for project {project_id} directly.")
        
        # ADR-001: Execute handles start/reset/end internally
        service.execute(project)
        
        logger.info(f"Step '{step_name}' for project {project_id} completed successfully.")

    def _orchestrate_project_pipeline(self, project_id: str):
        logger.info(f"Orchestrator started for project: {project_id}")

        while True:
            # Check if project was removed or stopped
            if project_id not in self.active_project_orchestrators:
                logger.info(f"Orchestrator for project {project_id} has been stopped.")
                break

            all_steps_completed = True
            for step_name in self.pipeline_config['execution_order']:
                if not self.is_step_complete(project_id, step_name):
                    with self._lock:
                        if f"{project_id}_{step_name}" not in self.active_processes:
                            all_steps_completed = False
                            break
            
            # If everything is done and no processes are active, we are finished.
            if all_steps_completed:
                active_for_project = [k for k in self.active_processes if k.startswith(f"{project_id}_")]
                if not active_for_project:
                    logger.info(f"All steps completed for project: {project_id}")
                    break

            eligible_steps = self._get_eligible_steps(project_id)
            for step_name in eligible_steps:
                key = f"{project_id}_{step_name}"
                
                # ATOMIC MARK AS ACTIVE BEFORE SPAWNING THREAD
                with self._lock:
                    if key in self.active_processes:
                        continue
                    self.active_processes[key] = True
                
                logger.info(f"Attempting to start eligible step '{step_name}' for project {project_id}")
                
                # Start step in a new thread. The thread will clear the 'active' mark in 'finally'.
                t = threading.Thread(target=self._run_single_step, args=(project_id, step_name))
                t.daemon = True
                t.start()

            time.sleep(1)

    def start_project_pipeline(self, project_id: str):
        if project_id in self.active_project_orchestrators:
            logger.warning(f"Orchestrator already running for project {project_id}")
            return

        orchestrator_thread = threading.Thread(target=self._orchestrate_project_pipeline, args=(project_id,))
        orchestrator_thread.daemon = True
        self.active_project_orchestrators[project_id] = orchestrator_thread
        orchestrator_thread.start()
        logger.info(f"Pipeline orchestration for project {project_id} initiated.")

    def stop_project_pipeline(self, project_id: str):
        logger.info(f"Stopping orchestrator for project {project_id}")
        if project_id in self.active_project_orchestrators:
            del self.active_project_orchestrators[project_id]

    def run_pipeline(self, project_id: str):
        """Executes the full pipeline in order as defined in configuration."""
        for step_name in self.pipeline_config['execution_order']:
            step_config = self.pipeline_config['steps'].get(step_name)
            if not step_config or not step_config.get('auto_run', True):
                continue
            
            self.run_step(project_id, step_name)
