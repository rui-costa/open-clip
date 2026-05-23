from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any
import abc
import uuid
import shutil
import os
import json

from backend.src.naming import generate_random_name
from backend.src.exceptions import ProjectNotFoundError
from backend.src.models import ProjectMetadata, ProjectSettings
from backend.src.fs_repository import FileSystemRepository

class BaseController(abc.ABC):
    """
    Abstract base class for service controllers.
    """
    pass

class ProjectManager(BaseController):
    def __init__(self, base_dir: str = "projects", repo: Optional[FileSystemRepository] = None):
        self.base_dir = Path(base_dir).resolve()
        self.repo = repo or FileSystemRepository()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _validate_path(self, path: Path) -> Path:
        """
        Ensures the given path is contained within the base project directory.
        Raises PermissionError if the path escapes the base directory.
        """
        resolved_path = path.resolve()
        if not resolved_path.is_relative_to(self.base_dir):
            raise PermissionError(f"Access denied: Path {resolved_path} is outside the projects directory.")
        return resolved_path

    def list_projects(self) -> list[str]:

        return self.repo.list_dirs(str(self.base_dir))

    def get_project_path(self, project_id: str) -> Path:
        return self._validate_path(self.base_dir / project_id)

    def get_metadata(self, project_id: str) -> ProjectMetadata:
        path = self.get_project_path(project_id) / "metadata.json"
        if not self.repo.exists(str(path)):
            raise ProjectNotFoundError(f"Metadata not found for project {project_id}")
        data = self.repo.read_json(str(path))
        
        return ProjectMetadata(
            project_id=data["project_id"],
            name=data["name"],
            created_at=datetime.fromisoformat(data["created_at"]),
            original_file=data.get("original_file"),
            highlights_file=data.get("highlights_file"),
            highlights=data.get("highlights", []),
            transcription_file=data.get("transcription_file"),
            video_metadata=data.get("video_metadata", {}),
            settings=ProjectSettings(**data.get("settings", {})),
            components=data.get("components", {}),
            clips=data.get("clips", []),
            status=data.get("status")
        )

    def save_project_metadata(self, project_id: str, metadata: ProjectMetadata) -> None:
        path = self.get_project_path(project_id) / "metadata.json"
        self.repo.save_object(str(path), metadata)

    def create_project(self, project_id: Optional[str] = None, name: Optional[str] = None, file_path: Optional[str] = None, aspect_ratio: str = "9:16", resolution: Optional[str] = None) -> Path:
        project_id = project_id or str(uuid.uuid4())
        project_path = self.get_project_path(project_id)

        project_path.mkdir(parents=True, exist_ok=True)
        (project_path / "clips").mkdir(exist_ok=True)

        # Copy source file into project directory if provided
        source_file_path = None
        source_filename = None
        if file_path:
            if not self.repo.exists(file_path):
                raise FileNotFoundError(f"Source file not found: {file_path}")
            # Copy the file to the project directory, preserving the original filename
            source_filename = os.path.basename(file_path)
            source_file_path = str(project_path / source_filename)
            shutil.copy2(file_path, source_file_path)

        metadata = ProjectMetadata(
            project_id=project_id,
            name=name or generate_random_name(),
            created_at=datetime.now(),
            original_file=source_file_path,
            highlights_file=None,
            transcription_file=None,
            settings=ProjectSettings(
                aspect_ratio=aspect_ratio,
                resolution=resolution,
                source_file=source_filename
            )
        )
        self.save_project_metadata(project_id, metadata)
        return project_path

    def update_metadata_field(self, project_id: str, field: str, value: Any) -> None:
        metadata = self.get_metadata(project_id)
        setattr(metadata, field, value)
        self.save_project_metadata(project_id, metadata)

    def update_project_name(self, project_id: str, new_name: str) -> bool:
        self.update_metadata_field(project_id, "name", new_name)
        return True

    def delete_component(self, project_id: str, component_name: str) -> bool:
        metadata = self.get_metadata(project_id)
        if component_name in metadata.components:
            comp_path = metadata.components[component_name]
            if os.path.exists(comp_path):
                os.remove(comp_path)
            del metadata.components[component_name]
            self.save_project_metadata(project_id, metadata)
            return True
        return False

    def get_component(self, project_id: str, component_name: str) -> Any:
        metadata = self.get_metadata(project_id)
        if component_name in metadata.components:
            comp_path = metadata.components[component_name]
            with open(comp_path, "r") as f:
                return json.load(f)
        return None

    def update_step_status(self, project_id: str, step_name: str, status: Optional[str] = None, started_at: Optional[str] = None, ended_at: Optional[str] = None):
        metadata = self.get_metadata(project_id)
        if status:
            metadata.status = status
        # Note: Dynamic status fields might need to be handled via a custom dictionary or adding them to the dataclass
        # For now, let's keep it simple.
        self.save_project_metadata(project_id, metadata)

    def get_highlights(self, project_id: str):
        metadata = self.get_metadata(project_id)
        # We allow empty list as a valid state (e.g. all clips deleted)
        return {"highlights": metadata.highlights}

    def get_transcription(self, project_id: str):
        metadata = self.get_metadata(project_id)
        if not metadata.transcription_file or not self.repo.exists(metadata.transcription_file):
            raise ProjectNotFoundError("Transcription file not found")
        return self.repo.read_json(metadata.transcription_file)

    def get_video_meta(self, project_id: str):
        metadata = self.get_metadata(project_id)
        if not metadata.video_metadata:
            raise ProjectNotFoundError("Video metadata not found in project metadata")
        return metadata.video_metadata

    def save_task_result(self, project_id: str, prompt_filename: str, data: Any) -> str:
        metadata = self.get_metadata(project_id)
        project_path = self.get_project_path(project_id)
        
        base_name = os.path.splitext(prompt_filename)[0].lower()
        json_filename = f"{base_name}.json"
        
        if base_name == "video_meta":
            metadata.video_metadata = data
            self.save_project_metadata(project_id, metadata)
            return str(project_path / "metadata.json")

        json_path = project_path / json_filename
        
        metadata_key_map = {
            "highlights.json": "highlights_file",
            "transcription.json": "transcription_file"
        }
        
        metadata_key = metadata_key_map.get(json_filename, f"{base_name}_file")
        
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
            
        setattr(metadata, metadata_key, str(json_path))
        self.save_project_metadata(project_id, metadata)
        
        return str(json_path)

    def save_highlights(self, project_id: str, highlights_data: Any):
        metadata = self.get_metadata(project_id)
        # Assuming highlights_data is a dictionary with a 'highlights' key
        metadata.highlights = highlights_data.get('highlights', [])
        self.save_project_metadata(project_id, metadata)

    def save_transcription(self, project_id: str, transcription_data: Any):
        metadata = self.get_metadata(project_id)
        if not metadata.transcription_file:
            metadata.transcription_file = str(self.get_project_path(project_id) / "transcription.json")
            self.save_project_metadata(project_id, metadata)
            
        self.repo.write_json(metadata.transcription_file, transcription_data)

    def delete_clip(self, project_id: str, index: int) -> bool:
        metadata = self.get_metadata(project_id)
        # Ensure that metadata.highlights has data if it was set via highlights_file previously
        if not metadata.highlights and metadata.highlights_file and self.repo.exists(metadata.highlights_file):
            highlights_data = self.repo.read_json(metadata.highlights_file)
            metadata.highlights = highlights_data.get("highlights", [])
            
        if 0 <= index < len(metadata.highlights):
            clip_filename = f"clip_{index:03d}.mp4"
            clip_path = self.get_project_path(project_id) / "clips" / clip_filename
            if clip_path.exists():
                clip_path.unlink()
            
            # Remove from metadata
            metadata.highlights.pop(index)
            
            # Save the updated metadata back to metadata.json
            self.save_project_metadata(project_id, metadata)
            
            # Rename subsequent clips
            for i in range(index + 1, len(metadata.highlights) + 1):
                old_path = self.get_project_path(project_id) / "clips" / f"clip_{i:03d}.mp4"
                new_path = self.get_project_path(project_id) / "clips" / f"clip_{i-1:03d}.mp4"
                if old_path.exists():
                    old_path.rename(new_path)
            return True
        return False

    def delete_project(self, project_id: str) -> bool:
        project_path = self.get_project_path(project_id)
        if os.path.exists(project_path):
            shutil.rmtree(project_path)
            return True
        return False

    def get_clip_video_path(self, project_id: str, clip_name: str) -> str:
        clip_path = os.path.join(self.get_project_path(project_id), "clips", clip_name)
        if not os.path.exists(clip_path):
            raise ProjectNotFoundError("Clip video not found")
        return clip_path

    def get_file_mtime(self, component_path: str) -> Optional[float]:
        if os.path.exists(component_path):
            return os.path.getmtime(component_path)
        return None
