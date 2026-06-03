from dataclasses import dataclass, asdict, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json
import csv

@dataclass
class WordMapEntry:
    word: str
    start: float
    end: float

@dataclass
class WordMap:
    entries: List[WordMapEntry] = field(default_factory=list)

    def load(self, project: 'Project'):
        path = project.get_artifact_path("word_map_file")
        self.entries = []
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                self.entries.append(WordMapEntry(
                    word=row["word"],
                    start=float(row["start"]),
                    end=float(row["end"])
                ))

@dataclass
class ProjectFileSettings:
    transcription_file: str = "transcription.txt"
    word_map_file: str = "word_map.csv"
    original_file: str = "original.mp4"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

# ... inside Project class ...

@dataclass
class Highlights:
    def __init__(self, items: List[Dict[str, Any]], project: 'Project'):
        self.highlights = []
        for item in items:
            if isinstance(item, dict):
                h = Highlight.from_json(item, project)
                if h.start > 0 or h.end > 0:
                    self.highlights.append(h)

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

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, data: Dict[str, Any], project: 'Project') -> 'Highlight':
        instance = cls(
            highlight_text=data.get("highlight_text", ""),
            viral_hook_text=data.get("viral_hook_text", ""),
            video_description_for_x=data.get("video_description_for_x", ""),
            video_description_for_reddit=data.get("video_description_for_reddit", ""),
            video_description_for_linkedin=data.get("video_description_for_linkedin", ""),
            video_title_for_youtube_short=data.get("video_title_for_youtube_short", ""),
            start=0.0,
            end=0.0
        )
        instance.find_timestamps(project)
        return instance

    def find_timestamps(self, project: 'Project') -> bool:
        all_words = project.word_map.entries
        snippet = self.highlight_text

        if not snippet:
            self.start, self.end = 0.0, 0.0
            return False

        snippet_words = snippet.strip().split()
        if not snippet_words:
            self.start, self.end = 0.0, 0.0
            return False

        normalized_snippet = [w.strip(".,!?\"'").lower() for w in snippet_words]
        CHUNK_SIZE = 5

        # Strategy 1: Anchor-Based
        if len(normalized_snippet) >= CHUNK_SIZE * 2:
            start_anchor = normalized_snippet[:CHUNK_SIZE]
            end_anchor = normalized_snippet[-CHUNK_SIZE:]

            start_idx = -1
            for i in range(len(all_words) - CHUNK_SIZE + 1):
                if all([all_words[i+j].word.strip(".,!?\"'").lower() == start_anchor[j] for j in range(CHUNK_SIZE)]):
                    start_idx = i
                    break

            if start_idx != -1:
                end_idx = -1
                for i in range(start_idx + CHUNK_SIZE, len(all_words) - CHUNK_SIZE + 1):
                    if all([all_words[i+j].word.strip(".,!?\"'").lower() == end_anchor[j] for j in range(CHUNK_SIZE)]):
                        end_idx = i

                if end_idx != -1:
                    self.start = all_words[start_idx].start
                    self.end = all_words[end_idx + CHUNK_SIZE - 1].end
                    return True

        # Strategy 2: Fuzzy
        MAX_GAP = 3
        for i in range(len(all_words)):
            if all_words[i].word.strip(".,!?\"'").lower() == normalized_snippet[0]:
                current_map_idx = i
                match_count = 1

                while match_count < len(normalized_snippet):
                    found_next = False
                    for gap in range(1, MAX_GAP + 2):
                        next_idx = current_map_idx + gap
                        if next_idx >= len(all_words):
                            break
                        if all_words[next_idx].word.strip(".,!?\"'").lower() == normalized_snippet[match_count]:
                            current_map_idx = next_idx
                            match_count += 1
                            found_next = True
                            break
                    if not found_next:
                        break

                if match_count == len(normalized_snippet):
                    self.start = all_words[i].start
                    self.end = all_words[current_map_idx].end
                    return True

        self.start, self.end = 0.0, 0.0
        return False

@dataclass
class VideoComponent:
    index: int
    title: str
    summary: str
    post_for_x: str
    post_for_reddit: str
    post_for_linkedin: str
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
@dataclass
class VideoMetadata:
    components: List[VideoComponent] = field(default_factory=list)
    top_recommendations: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_llm(cls, data: Dict[str, Any]) -> 'VideoMetadata':
        if isinstance(data, list):
            data = {"components": data, "top_recommendations": []}

        items = data.get("components") or data.get("titles", [])
        components = []
        for item in items:
            if isinstance(item, dict):
                if 'summary' not in item and 'reason' in item:
                    item['summary'] = item['reason']
                components.append(VideoComponent(**item))

        return cls(components=components, top_recommendations=data.get("top_recommendations", []))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "components": [c.to_dict() for c in self.components],
            "top_recommendations": self.top_recommendations
        }

@dataclass
class ProjectSettings:
    aspect_ratio: str
    resolution: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class Clip:
    filename: str
    original_start: float
    original_end: float
    processed_start: float
    processed_end: float
    text: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def __getitem__(self, key):
        return getattr(self, key)


@dataclass
class Project:
    project_id: str = None
    name: str = None
    created_at: datetime = field(default_factory=datetime.now)
    files: ProjectFileSettings = field(default_factory=ProjectFileSettings)
    highlights: List[Highlight] = field(default_factory=list)
    video_metadata: VideoMetadata = field(default_factory=lambda: VideoMetadata([], []))
    settings: ProjectSettings = field(default_factory=lambda: ProjectSettings("16:9", "1080p"))
    clips: List[Clip] = field(default_factory=list)
    status: Optional[str] = None
    step_statuses: Dict[str, str] = field(default_factory=dict)
    base_path: Path = field(default=Path("projects"))
    base_directory: str = "projects"
    clip_base_directory: str = "clips"
    _word_map: Optional[WordMap] = field(default=None, init=False, repr=False)

    @property
    def word_map(self) -> WordMap:
        if self._word_map is None:
            self._word_map = WordMap()
            self._word_map.load(self)
        return self._word_map

    def __post_init__(self):
        if self.project_id:
            self.load(self.project_id)
        else:
            import uuid
            from backend.src.utils import generate_random_name
            self.project_id = str(uuid.uuid4())
            self.name = generate_random_name()
            self.save()  # Persist the new project immediately


    def load(self, project_id: str):
        project_path = Path(self.base_directory) / project_id / "metadata.json"
        with open(project_path, 'r') as f:
            metadata = json.load(f)
        self.from_dict(metadata)

        #load static paths

    def get_clip_path(self, clip: str) -> str:
        return self.base_directory + "/" + self.project_id + "/" + self.clip_base_directory + "/" + clip

    def get_artifact_path(self, field: str) -> Path:
        """Returns the full Path for a file artifact defined in files."""
        filename = getattr(self.files, field)
        return Path(self.base_directory) / self.project_id / filename

    def save(self):
        project_path = Path(self.base_directory) / self.project_id
        project_path.mkdir(parents=True, exist_ok=True)
        with open(project_path / "metadata.json", 'w') as f:
            json.dump(self.to_dict(), f, indent=4)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "files": self.files.to_dict(),
            "highlights": [h.to_dict() for h in self.highlights],
            "video_metadata": self.video_metadata.to_dict(),
            "settings": self.settings.to_dict(),
            "clips": [c.to_dict() for c in self.clips],
            "status": self.status,
            "step_statuses": self.step_statuses
        }

    def from_dict(self, metadata: Dict[str, Any]):
        self.project_id = metadata["project_id"]
        self.name = metadata["name"]
        self.created_at = datetime.fromisoformat(metadata["created_at"])
        self.files = ProjectFileSettings(**metadata["files"])
        self.highlights = [Highlight(**h) for h in metadata["highlights"]]

        comp = [VideoComponent(**c) for c in metadata["video_metadata"]["components"]]
        self.video_metadata = VideoMetadata(comp, metadata["video_metadata"]["top_recommendations"])
        
        settings_data = {k: v for k, v in metadata["settings"].items() if k in ["aspect_ratio", "resolution"]}
        self.settings = ProjectSettings(**settings_data)
        
        self.clips = [Clip(**c) for c in metadata["clips"]]
        self.status = metadata.get("status")
        self.step_statuses = metadata.get("step_statuses", {})

    def set_step_status(self, step: str, status: str):
        self.step_statuses[step] = status
        self.save()

    def set_clips(self, clips: List[Clip]):
        self.clips = clips
        self.save()

    def set_property(self, key: str, value: Any):
        setattr(self, key, value)
        self.save()

    def delete_clip(self, index: int):
        if 0 <= index < len(self.clips):
            clip = self.clips.pop(index)
            clip_path = Path(self.get_clip_path(clip.filename))
            if clip_path.exists():
                clip_path.unlink()
            self.save()