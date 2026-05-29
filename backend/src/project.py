from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

@dataclass
class ProjectFileSettings:
    transcription_file: str
    word_map_file: str
    original_file: str

@dataclass
class Highlight:
    highlight_text: str
    viral_hook_text: str
    video_description_for_x: str
    video_description_for_reddit: str
    video_description_for_linkedin: str
    video_title_for_youtube_short: str
    start: float
    end: float

@dataclass
class VideoComponent:
    index: int
    title: str
    summary: str
    post_for_x: str
    post_for_reddit: str
    post_for_linkedin: str
    reason: str

@dataclass
class VideoMetadata:
    components: List[VideoComponent]
    top_recommendations: List[Dict[str, Any]]

    def get(self, key, default=None):
        return getattr(self, key, default)

@dataclass
class ProjectSettings:
    aspect_ratio: str
    resolution: str
    source_file: str

@dataclass
class Clip:
    filename: str
    original_start: float
    original_end: float
    processed_start: float
    processed_end: float
    text: str

    def __getitem__(self, key):
        return getattr(self, key)

@dataclass
class Project:
    project_id: str
    name: str
    created_at: datetime
    files: ProjectFileSettings
    highlights: List[Highlight]
    video_metadata: VideoMetadata
    settings: ProjectSettings
    clips: List[Clip]
    status: Optional[str] = None
    step_statuses: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Project':
        return cls(
            project_id=data["project_id"],
            name=data["name"],
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data["created_at"], str) else data["created_at"],
            files=ProjectFileSettings(**data["files"]),
            highlights=[Highlight(**h) for h in data["highlights"]],
            video_metadata=VideoMetadata(
                components=[VideoComponent(**c) for c in data["video_metadata"]["components"]],
                top_recommendations=data["video_metadata"]["top_recommendations"]
            ),
            settings=ProjectSettings(**data["settings"]),
            clips=[Clip(**c) for c in data["clips"]],
            status=data.get("status"),
            step_statuses=data.get("step_statuses", {})
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "files": asdict(self.files),
            "highlights": [asdict(h) for h in self.highlights],
            "video_metadata": {
                "components": [asdict(c) for c in self.video_metadata.components],
                "top_recommendations": self.video_metadata.top_recommendations
            },
            "settings": asdict(self.settings),
            "clips": [asdict(c) for c in self.clips],
            "status": self.status,
            "step_statuses": self.step_statuses
        }
