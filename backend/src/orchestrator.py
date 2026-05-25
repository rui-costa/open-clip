import json
import logging
import threading
import time
from pathlib import Path
from typing import Dict, Any, List, Optional
from backend.src.manager import ProjectManager

logger = logging.getLogger(__name__)

# Mock Args class for CLI handlers
class MockArgs:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

class PipelineOrchestrator:
    ALLOWED_CLI_COMMANDS = {
        "transcribe",
        "highlights",
        "metadata",
        "clipper",
        "upload"
    }

    def __init__(self, projects_base_dir: str = "projects", config_path: str = "backend/config/pipeline.json", active_processes: Dict[str, Any] = None):
        self.project_manager = ProjectManager(base_dir=projects_base_dir)
        self.config_path = Path(config_path)
        self.pipeline_config = self._load_pipeline_config()
        self.active_project_orchestrators: Dict[str, threading.Thread] = {}
        # Shared state for active steps across all projects
        self.active_processes = active_processes if active_processes is not None else {}
        self._lock = threading.Lock()

    def _load_pipeline_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Pipeline config not found at {self.config_path}")
        with open(self.config_path, 'r') as f:
            return json.load(f)

    def reload_config(self):
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
            
            # Check if already running (thread-safe check)
            with self._lock:
                if f"{project_id}_{step_name}" in self.active_processes:
                    continue

            dependencies = step_config.get('depends_on', [])
            all_deps_complete = all(self.is_step_complete(project_id, dep) for dep in dependencies)

            if all_deps_complete:
                eligible_steps.append(step_name)
        return eligible_steps

    def _run_single_step(self, project_id: str, step_name: str):
        """Executes a single step using direct CLI handler calls."""
        step_config = self.pipeline_config['steps'].get(step_name)
        if not step_config:
            logger.error(f"Attempted to run unknown step: {step_name}")
            return

        command = step_config['command']
        if command not in self.ALLOWED_CLI_COMMANDS:
            logger.error(f"Security Alert: Unauthorized command '{command}' attempted for step '{step_name}'. Execution blocked.")
            return

        # Perform local import to avoid loading heavy ML libraries at module load time
        # and to keep dependencies isolated to the execution context.
        from backend.cli import (
            handle_transcribe, 
            handle_highlights, 
            handle_metadata, 
            handle_clipper, 
            handle_upload
        )
        handlers = {
            "transcribe": handle_transcribe,
            "highlights": handle_highlights,
            "metadata": handle_metadata,
            "clipper": handle_clipper,
            "upload": handle_upload
        }
        handler = handlers.get(command)

        if not handler:
            logger.error(f"No handler found for command: {command}")
            self.project_manager.update_step_status(project_id, step_name, status="failed")
            with self._lock:
                key = f"{project_id}_{step_name}"
                if key in self.active_processes: del self.active_processes[key]
            return

        logger.info(f"Starting step '{step_name}' for project {project_id} directly.")
        
        try:
            # Build mock args based on what the handler expects
            args = MockArgs(
                project_id=project_id,
                model="base",
                language=None,
                clip_index=None,
                privacy="private",
                credentials_dir="./backend/youtube_credentials"
            )
            # CALL THE PYTHON CODE DIRECTLY
            handler(args)
            
            logger.info(f"Step '{step_name}' for project {project_id} completed successfully.")
            self.project_manager.update_step_status(project_id, step_name, status="completed")
        except Exception as e:
            logger.error(f"Error running step '{step_name}' for project {project_id}: {e}", exc_info=True)
            self.project_manager.update_step_status(project_id, step_name, status="failed")
        finally:
            with self._lock:
                key = f"{project_id}_{step_name}"
                if key in self.active_processes:
                    del self.active_processes[key]

    def _orchestrate_project_pipeline(self, project_id: str):
        logger.info(f"Orchestrator started for project: {project_id}")
        self.project_manager.update_step_status(project_id, "pipeline", status="running")

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
                    self.project_manager.update_step_status(project_id, "pipeline", status="completed")
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
                self.project_manager.update_step_status(project_id, step_name, status="running")
                
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
        
        # Note: We don't forcefully kill the task threads because they are Python threads
        # and ML operations (like Whisper) are often holding the GIL or running in C extensions.
        # They will finish their current step and stop.

    def reset_project_pipeline(self, project_id: str):
        logger.info(f"Resetting pipeline for project: {project_id}")
        self.stop_project_pipeline(project_id)
        
        project_path = Path(self.project_manager.get_project_path(project_id))
        if (project_path / "transcription.txt").exists(): (project_path / "transcription.txt").unlink()
        if (project_path / "word_map.csv").exists(): (project_path / "word_map.csv").unlink()

        metadata = self.project_manager.get_metadata(project_id)
        metadata.highlights = []; metadata.video_metadata = {}; metadata.transcription_file = None
        metadata.clips = []
        metadata.clipper_start = None
        metadata.clipper_end = None
        if "word_map_file" in metadata.components: del metadata.components["word_map_file"]
        if "clips_dir" in metadata.components: del metadata.components["clips_dir"]
        self.project_manager.save_project_metadata(project_id, metadata)
        
        clips_dir = project_path / "clips"
        if clips_dir.exists():
            import shutil
            shutil.rmtree(clips_dir)
            clips_dir.mkdir(exist_ok=True)
