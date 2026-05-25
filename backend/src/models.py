from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any

@dataclass
class ProjectSettings:
    aspect_ratio: str = "9:16"
    resolution: Optional[str] = None
    source_file: Optional[str] = None

@dataclass
class ProjectMetadata:
    project_id: str
    name: str
    created_at: datetime
    original_file: Optional[str] = None
    highlights_file: Optional[str] = None
    highlights: List[Dict[str, Any]] = field(default_factory=list)
    transcription_file: Optional[str] = None
    video_metadata: Optional[Dict[str, Any]] = field(default_factory=dict)
    settings: ProjectSettings = field(default_factory=ProjectSettings)
    components: Dict[str, str] = field(default_factory=dict)
    clips: List[Dict[str, Any]] = field(default_factory=list)
    status: Optional[str] = None
    step_statuses: Dict[str, str] = field(default_factory=dict)
    clipper_start: Optional[float] = None
    clipper_end: Optional[float] = None
