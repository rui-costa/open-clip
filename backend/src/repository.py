import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

from backend.src.dataclasses.data import Project, Clip, Highlight

class ProjectRepository:
    @staticmethod
    def save(project: Project) -> None:
        metadata_path = project.base_path / "metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(project.to_dict(), f, indent=2, default=str)

    @staticmethod
    def load(project_id: str, base_dir: Path = Path("projects")) -> Project:
        project_path = base_dir / project_id
        metadata_path = project_path / "metadata.json"
        
        with open(metadata_path, 'r') as f:
            data = json.load(f)
            
        return Project.from_dict(data, project_path)

    @staticmethod
    def create(name: str, file_path: str, base_dir: Path = Path("projects")) -> Project:
        pid = str(uuid.uuid4())
        project_path = base_dir / pid
        project_path.mkdir(parents=True, exist_ok=True)
        
        data = {
            "project_id": pid,
            "name": name,
            "created_at": datetime.now().isoformat(),
            "files": {"transcription_file": "", "word_map_file": "", "original_file": file_path},
            "highlights": [],
            "video_metadata": {"components": [], "top_recommendations": []},
            "settings": {"aspect_ratio": "9:16", "resolution": "FHD", "source_file": file_path},
            "clips": [],
            "status": "created",
            "step_statuses": {}
        }
        
        project = Project.from_dict(data, project_path)
        ProjectRepository.save(project)
        return project

    @staticmethod
    def set_step_status(project: Project, step: str, status: str) -> None:
        project.step_statuses[step] = status
        ProjectRepository.save(project)

    @staticmethod
    def set_clips(project: Project, clips: List[Clip]) -> None:
        project.clips = clips
        ProjectRepository.save(project)

    @staticmethod
    def set_highlights(project: Project, highlights: List[Highlight]) -> None:
        project.highlights = highlights
        ProjectRepository.save(project)
