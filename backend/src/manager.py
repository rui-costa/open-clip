from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import uuid
import shutil
import os

from backend.src.naming import generate_random_name
from backend.src.exceptions import ProjectNotFoundError
from backend.src.project import Project
from backend.src.fs_repository import FileSystemRepository

class ProjectManager:
    def __init__(self, base_dir: str = "projects", repo: Optional[FileSystemRepository] = None):
        self.base_dir = Path(base_dir).resolve()
        self.repo = repo or FileSystemRepository()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _validate_path(self, path: Path) -> Path:
        resolved_path = path.resolve()
        if not resolved_path.is_relative_to(self.base_dir):
            raise PermissionError(f"Access denied: Path {resolved_path} is outside the projects directory.")
        return resolved_path

    def create_project(self, name: Optional[str] = None, file_path: Optional[str] = None, project_id: Optional[str] = None) -> Path:
        pid = project_id or str(uuid.uuid4())
        project_path = self._validate_path(self.base_dir / pid)
        project_path.mkdir(parents=True, exist_ok=True)
        
        initial_data = {
            "project_id": pid,
            "name": name or generate_random_name(),
            "created_at": datetime.now().isoformat(),
            "files": {"transcription_file": "", "word_map_file": "", "original_file": file_path or ""},
            "highlights": [],
            "video_metadata": {"components": [], "top_recommendations": []},
            "settings": {"aspect_ratio": "9:16", "resolution": "FHD", "source_file": file_path or ""},
            "clips": [],
            "status": "created",
            "step_statuses": {}
        }
        self.repo.write_json(str(project_path / "metadata.json"), initial_data)
        return project_path

    def get_project(self, project_id: str) -> Project:
        path = self._validate_path(self.base_dir / project_id) / "metadata.json"
        if not self.repo.exists(str(path)):
            raise ProjectNotFoundError(f"Project {project_id} not found")
        data = self.repo.read_json(str(path))
        data["project_id"] = project_id
        return Project.from_dict(data)

    def save_project(self, project: Project) -> None:
        path = self._validate_path(self.base_dir / project.project_id) / "metadata.json"
        self.repo.write_json(str(path), project.to_dict())

    def get_project_path(self, project_id: str) -> Path:
        return self._validate_path(self.base_dir / project_id)

    def get_metadata(self, project_id: str) -> Project:
        return self.get_project(project_id)

    def get_highlights(self, project_id: str) -> List[Any]:
        return self.get_project(project_id).highlights

    def get_video_meta(self, project_id: str) -> Any:
        return self.get_project(project_id).video_metadata

    def get_clip_video_path(self, project_id: str, clip_filename: str) -> Path:
        return self.get_project_path(project_id) / "clips" / clip_filename

    def update_project_name(self, project_id: str, name: str) -> None:
        p = self.get_project(project_id)
        p.name = name
        self.save_project(p)
    
    def update_metadata_field(self, project_id: str, field: str, value: Any) -> None:
        p = self.get_project(project_id)
        if hasattr(p, field):
            setattr(p, field, value)
            self.save_project(p)
    
    def delete_clip(self, project_id: str, clip_idx: int) -> bool:
        p = self.get_project(project_id)
        if 0 <= clip_idx < len(p.clips):
            clip = p.clips.pop(clip_idx)
            clip_path = self.get_clip_video_path(project_id, clip.filename)
            if clip_path.exists():
                clip_path.unlink()
            self.save_project(p)
            return True
        return False

    def save_task_result(self, project_id: str, filename: str, data: Any) -> Path:
        path = self.get_project_path(project_id) / filename
        self.repo.save_object(str(path), data)
        return path
        
    def delete_project(self, project_id: str) -> bool:
        project_path = self._validate_path(self.base_dir / project_id)
        if project_path.exists():
            shutil.rmtree(project_path)
            return True
        return False

ProjectRepository = ProjectManager
