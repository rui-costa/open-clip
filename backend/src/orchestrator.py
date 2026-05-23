import json
import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from backend.src.manager import ProjectManager

logger = logging.getLogger(__name__)

class PipelineOrchestrator:
    # Whitelist of allowed commands that can be passed to backend.cli
    # This prevents arbitrary command execution if the pipeline config is compromised.
    ALLOWED_CLI_COMMANDS = {
        "transcribe",
        "highlights",
        "metadata",
        "clipper",
        "upload"
    }

    def __init__(self, projects_base_dir: str = "projects", config_path: str = "backend/config/pipeline.json", active_processes: Dict[str, subprocess.Popen] = None):

        self.project_manager = ProjectManager(base_dir=projects_base_dir)
        self.config_path = Path(config_path)
        self.pipeline_config = self._load_pipeline_config()
        self.active_project_orchestrators: Dict[str, threading.Thread] = {}
        # Shared dictionary for active subprocesses, optionally injected
        self.active_processes = active_processes if active_processes is not None else {}

    def _load_pipeline_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Pipeline config not found at {self.config_path}")
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def reload_config(self):
        """Reloads the pipeline configuration from disk."""
        logger.info("Reloading pipeline configuration...")
        self.pipeline_config = self._load_pipeline_config()

    def is_step_complete(self, project_id: str, step_name: str) -> bool:
        project_path = Path(self.project_manager.get_project_path(project_id))
        metadata = self.project_manager.get_metadata(project_id)
        
        if step_name == "transcribe":
            full_path = project_path / "transcription.txt"
            return full_path.is_file() and full_path.stat().st_size > 0
        
        if step_name == "highlights":
            return len(metadata.highlights) > 0
        
        if step_name == "metadata":
            return bool(metadata.video_metadata)
            
        if step_name == "clipper":
            full_path = project_path / "clips"
            return full_path.is_dir() and any(full_path.iterdir())
        
        if step_name == "upload":
            # Upload is complete if we have upload records in components
            return len(metadata.components.get("uploads", [])) > 0

        return False
    
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
            
            # Check if already running by this orchestrator instance
            if f"{project_id}_{step_name}" in self.active_processes:
                continue

            dependencies = step_config.get('depends_on', [])
            all_deps_complete = all(self.is_step_complete(project_id, dep) for dep in dependencies)

            if all_deps_complete:
                eligible_steps.append(step_name)
        return eligible_steps

    def _run_single_step(self, project_id: str, step_name: str):
        step_config = self.pipeline_config['steps'].get(step_name)
        if not step_config:
            logger.error(f"Attempted to run unknown step: {step_name}")
            return

        command = step_config['command']
        if command not in self.ALLOWED_CLI_COMMANDS:
            logger.error(f"Security Alert: Unauthorized command '{command}' attempted for step '{step_name}'. Execution blocked.")
            return

        cmd_args = ["./.venv/bin/python3", "-m", "backend.cli", command, project_id]
        logger.info(f"Starting step '{step_name}' for project {project_id} with command: {cmd_args}")
        
        try:
            process = subprocess.Popen(cmd_args)
            self.active_processes[f"{project_id}_{step_name}"] = process
            process.wait() # Wait for the subprocess to complete
            del self.active_processes[f"{project_id}_{step_name}"]
            
            if process.returncode == 0:
                logger.info(f"Step '{step_name}' for project {project_id} completed successfully.")
                self.project_manager.update_step_status(project_id, step_name, status="completed")
            else:
                logger.error(f"Step '{step_name}' for project {project_id} failed with exit code {process.returncode}.")
                self.project_manager.update_step_status(project_id, step_name, status="failed")

        except Exception as e:
            logger.error(f"Error running step '{step_name}' for project {project_id}: {e}")
            self.project_manager.update_step_status(project_id, step_name, status="failed")
            key = f"{project_id}_{step_name}"
            if key in self.active_processes:
                del self.active_processes[key]


    def _orchestrate_project_pipeline(self, project_id: str):
        logger.info(f"Orchestrator started for project: {project_id}")
        
        # Initial status update
        self.project_manager.update_step_status(project_id, "pipeline", status="running")

        while True:
            all_steps_completed = True
            for step_name in self.pipeline_config['execution_order']:
                if (not self.is_step_complete(project_id, step_name) and
                    f"{project_id}_{step_name}" not in self.active_processes):
                    all_steps_completed = False
                    break
            
            if all_steps_completed and not self.active_processes:
                logger.info(f"All steps completed for project: {project_id}")
                self.project_manager.update_step_status(project_id, "pipeline", status="completed")
                break

            eligible_steps = self._get_eligible_steps(project_id)
            for step_name in eligible_steps:
                logger.info(f"Attempting to start eligible step '{step_name}' for project {project_id}")
                threading.Thread(target=self._run_single_step, args=(project_id, step_name)).start()
                # Update status to running immediately, actual completion is handled in _run_single_step
                self.project_manager.update_step_status(project_id, step_name, status="running")


            time.sleep(1) # Poll every second

    def start_project_pipeline(self, project_id: str):
        if project_id in self.active_project_orchestrators:
            logger.warning(f"Orchestrator already running for project {project_id}")
            return

        orchestrator_thread = threading.Thread(target=self._orchestrate_project_pipeline, args=(project_id,))
        orchestrator_thread.daemon = True # Allow main program to exit even if threads are running
        self.active_project_orchestrators[project_id] = orchestrator_thread
        orchestrator_thread.start()
        logger.info(f"Pipeline orchestration for project {project_id} initiated.")

    def stop_project_pipeline(self, project_id: str):
        # This currently doesn't actually stop the _orchestrate_project_pipeline thread gracefully
        # It only stops the subprocesses. More advanced shutdown would require adding a stop event.
        logger.info(f"Stopping all active processes for project {project_id}")
        processes_to_terminate = [
            proc for key, proc in self.active_processes.items() if key.startswith(f"{project_id}_")
        ]
        for proc in processes_to_terminate:
            proc.terminate()
            proc.wait(timeout=5) # Give it a moment to terminate
        
        # Clean up active_processes entries
        keys_to_delete = [key for key in self.active_processes if key.startswith(f"{project_id}_")]
        for key in keys_to_delete:
            del self.active_processes[key]

        if project_id in self.active_project_orchestrators:
            # We don't join/kill the orchestrator thread here, relying on daemon=True
            del self.active_project_orchestrators[project_id]
            logger.info(f"Orchestrator for project {project_id} removed from active list (subprocesses terminated).")

    def reset_project_pipeline(self, project_id: str):
        """
        Resets the project pipeline to a clean state, erasing all intermediate outputs.
        """
        logger.info(f"Resetting pipeline for project: {project_id}")
        project_path = Path(self.project_manager.get_project_path(project_id))
        
        # 1. Remove transcription files
        transcription_txt = project_path / "transcription.txt"
        if transcription_txt.exists():
            transcription_txt.unlink()
            
        word_map_csv = project_path / "word_map.csv"
        if word_map_csv.exists():
            word_map_csv.unlink()

        # 2. Clear metadata in ProjectMetadata object
        metadata = self.project_manager.get_metadata(project_id)
        metadata.highlights = []
        metadata.video_metadata = {}
        metadata.transcription_file = None
        
        # Clear any component files related to transcription if they exist
        if "word_map_file" in metadata.components:
            del metadata.components["word_map_file"]
            
        self.project_manager.save_project_metadata(project_id, metadata)

        # 3. Clear clips directory
        clips_dir = project_path / "clips"
        if clips_dir.exists():
            for file in clips_dir.iterdir():
                file.unlink()
        
        # Clear clips list in metadata
        metadata = self.project_manager.get_metadata(project_id)
        metadata.clips = []
        self.project_manager.save_project_metadata(project_id, metadata)
        
        logger.info(f"Pipeline reset complete for project {project_id}")

