import os
import shutil
import logging
from dataclasses import asdict
from typing import List, Dict, Any, Tuple
from backend.src.dataclasses.data import Project, Clip
from backend.src.infrastructure.video_engine import OpenCVVideoEngine, Viewport

logger = logging.getLogger(__name__)

class Clipper:
    def reset_metadata(self, project: Project) -> None:
        """Clears the clips/ directory and resets clip state."""
        clips_dir = os.path.join(os.path.dirname(str(project.get_artifact_path("original_file"))), "clips")
        if os.path.exists(clips_dir):
            shutil.rmtree(clips_dir)
        os.makedirs(clips_dir, exist_ok=True)
        project.set_step_status("clipper", "pending")

    def start_service(self, project: Project) -> None:
        """Initializes the service and resets metadata."""
        self.reset_metadata(project)
        project.set_step_status("clipper", "running")

    async def execute(self, project: Project) -> List[Dict[str, Any]]:  # pragma: no cover
        """Executes clipping logic."""
        logger.info(f"Clipper executing for project={project.project_id}, highlight_count={len(project.highlights)}")
        self.start_service(project)
        try:
            engine = OpenCVVideoEngine("root/yolov8n.pt")
            input_path = str(project.get_artifact_path("original_file"))
            clips_dir = os.path.join(os.path.dirname(input_path), "clips")
            os.makedirs(clips_dir, exist_ok=True)
            logger.info(f"Clipper clips_dir={clips_dir}, exists={os.path.exists(clips_dir)}")
            
            for i, short in enumerate(project.highlights):
                start = max(0.0, float(short.start))
                end = float(short.end)
                filename = f"clip_{i:03d}.mp4"
                output_path = os.path.abspath(os.path.join(clips_dir, filename))
                
                logger.info(f"Clipper processing clip={i+1} of {len(project.highlights)} ({filename}), range={start}-{end}")
                engine.process_clip(
                    input_path, 
                    output_path, 
                    start, 
                    end, 
                    project.settings.aspect_ratio, 
                    project.settings.resolution
                )
                
                short.is_clip_generated = True
                short.generated_clip_filename = filename
                project.save()
            
            logger.info(f"Clipper completed for project={project.project_id}")
            self.end_service(project)
            return [h.to_dict() for h in project.highlights]
        except Exception as e:
            logger.error(f"Error executing clipper: {e}")
            project.set_step_status("clipper", "error")
            return []

    def end_service(self, project: Project) -> None:
        """Finalizes the service."""
        project.set_step_status("clipper", "completed")
