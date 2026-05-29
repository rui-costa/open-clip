from typing import Dict, Any, List
from pathlib import Path
from backend.src.project import Project
from backend.src.settings_manager import settings_manager
from backend.src.infrastructure.youtube_client import YoutubeClient

class Uploader:
    def __init__(self):
        pass

    def reset_metadata(self, project: Project) -> None:
        """Clears upload-related artifacts."""
        pass

    def start_service(self, project: Project) -> None:
        """Initializes the service."""
        self.reset_metadata(project)

    def end_service(self, project: Project) -> None:
        """Finalizes the service."""
        pass

    def execute(self, project: Project) -> List[Dict[str, Any]]:  # pragma: no cover
        self.start_service(project)
        client = YoutubeClient(api_key=settings_manager.get("youtube_api_key"))
        
        uploads_list = []
        for clip in project.clips:
            # Clips are stored in the project directory
            clip_path = str(Path("projects") / project.project_id / "clips" / clip.filename)
            
            result = client.upload_video(
                file_path=clip_path,
                title=clip.text[:100],
                description=f"Generated clip from {project.name}"
            )
            uploads_list.append(result)
        self.end_service(project)
        return uploads_list