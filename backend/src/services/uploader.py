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
        logger.info(f"Uploader executing for project={project.project_id}, clip_count={len(project.clips)}")
        self.start_service(project)
        client = YoutubeClient(api_key=settings_manager.get("youtube_api_key"))
        
        uploads_list = []
        for clip in project.clips:
            # Clips are stored in the project directory
            clip_path = str(Path("projects") / project.project_id / "clips" / clip.filename)
            
            logger.info(f"Uploader uploading clip={clip.filename} to YouTube")
            result = client.upload_video(
                file_path=clip_path,
                title=clip.text[:100],
                description=f"Generated clip from {project.name}"
            )
            logger.info(f"Uploader uploaded clip={clip.filename}, result_id={result.get('id')}")
            uploads_list.append(result)
        self.end_service(project)
        logger.info(f"Uploader completed for project={project.project_id}")
        return uploads_list