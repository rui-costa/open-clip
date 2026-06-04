import logging
from typing import Dict, Any, List
from pathlib import Path
from backend.src.dataclasses.data import Project
from backend.src.settings_manager import settings_manager
from backend.src.infrastructure.youtube_client import YoutubeClient

logger = logging.getLogger(__name__)

class Uploader:
    def __init__(self):
        pass

    def reset_metadata(self, project: Project) -> None:
        """Clears upload-related artifacts and updates project state."""
        project.set_property("uploads", [])
        project.set_step_status("upload", "pending")

    def start_service(self, project: Project) -> None:
        """Initializes the service."""
        self.reset_metadata(project)
        project.set_step_status("upload", "running")

    def end_service(self, project: Project) -> None:
        """Finalizes the service."""
        project.set_step_status("upload", "completed")

    async def execute(self, project: Project) -> List[Dict[str, Any]]:  # pragma: no cover
        logger.info(f"Uploader executing for project={project.project_id}, highlight_count={len(project.highlights)}")
        self.start_service(project)
        client = YoutubeClient()
        
        uploads_list = []
        for highlight in project.highlights:
            if not highlight.is_clip_generated or not highlight.generated_clip_filename:
                continue

            # Clips are stored in the project directory
            clip_path = str(Path(project.base_directory) / project.project_id / "clips" / highlight.generated_clip_filename)
            
            logger.info(f"Uploader uploading clip={highlight.generated_clip_filename} to YouTube")
            logger.info(f"Uploading with title: '{highlight.viral_hook_text}'")
            result = client.upload_video(
                file_path=clip_path,
                title=highlight.viral_hook_text,
                description=highlight.video_title_for_youtube_short
            )
            logger.info(f"Uploader uploaded clip={highlight.generated_clip_filename}, result_id={result.get('id')}")
            uploads_list.append(result)
        self.end_service(project)
        logger.info(f"Uploader completed for project={project.project_id}")
        return uploads_list