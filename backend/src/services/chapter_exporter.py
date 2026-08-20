"""Render the `chapters` LLM task output as YouTube chapters and timeline markers.

The chapters task stores `{"chapters": [{"chapter_time", "chapter_title"}]}` in
`project.llm_outputs`, with times as `HH:MM:SS` strings. Two outputs are derived
from it: the plain-text list YouTube parses out of a video description, and a
marker EDL in the same shape as the highlight markers.

Not part of the pipeline: the UI calls it through the API.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.src.services.marker_exporter import (
    DEFAULT_FPS,
    DEFAULT_RECORD_START,
    build_marker_edl,
    probe_fps,
)

logger = logging.getLogger(__name__)

TASK_NAME = "chapters"
MARKER_COLOR = "ResolveColorYellow"
# A chapter is a point in time; the last one has no successor to run up to, so
# its marker gets this length rather than a zero-width one.
LAST_MARKER_SECONDS = 5.0

# The schema names these keys, but a prompt edit is one word away from renaming
# them, and losing an export to that is not worth it.
TIME_KEYS = ("chapter_time", "time", "timestamp", "start", "start_time")
TITLE_KEYS = ("chapter_title", "title", "chapter_summary", "summary", "name")


class NoChaptersError(ValueError):
    """Raised when a project has no usable chapters to export."""


def parse_timestamp(value: Any) -> Optional[float]:
    """Parses `HH:MM:SS`, `MM:SS`, `SS`, or a number, into seconds."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return max(0.0, float(value))
    if not isinstance(value, str):
        return None

    parts = value.strip().split(":")
    if not parts or len(parts) > 3:
        return None
    try:
        numbers = [float(part) for part in parts]
    except ValueError:
        return None
    if any(number < 0 for number in numbers):
        return None

    seconds = 0.0
    for number in numbers:
        seconds = seconds * 60 + number
    return seconds


def format_timestamp(seconds: float, with_hours: bool) -> str:
    """YouTube-style `M:SS`, or `H:MM:SS` once any chapter passes the hour."""
    total = max(0, int(seconds))
    minutes, ss = divmod(total, 60)
    hours, mm = divmod(minutes, 60)
    if with_hours:
        return f"{hours}:{mm:02d}:{ss:02d}"
    return f"{minutes}:{ss:02d}"


def _first(item: Dict[str, Any], keys: Tuple[str, ...]) -> Any:
    for key in keys:
        if key in item:
            return item[key]
    return None


def extract_chapters(project) -> List[Tuple[float, str]]:
    """Returns `(seconds, title)` pairs in ascending time order."""
    output = (project.llm_outputs or {}).get(TASK_NAME)
    items = output.get(TASK_NAME) if isinstance(output, dict) else output
    if not isinstance(items, list):
        raise NoChaptersError(
            f"Project {project.project_id} has no chapters. Run the Chapters query first."
        )

    chapters: List[Tuple[float, str]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            logger.warning(f"Skipping chapter {index}: not an object")
            continue
        seconds = parse_timestamp(_first(item, TIME_KEYS))
        if seconds is None:
            logger.warning(f"Skipping chapter {index}: unreadable timestamp {_first(item, TIME_KEYS)!r}")
            continue
        title = _first(item, TITLE_KEYS)
        chapters.append((seconds, str(title).strip() if title else f"Chapter {index + 1}"))

    if not chapters:
        raise NoChaptersError(f"Project {project.project_id} has no readable chapters.")

    return sorted(chapters, key=lambda chapter: chapter[0])


def build_youtube_chapters(project) -> str:
    """The chapter list in the form YouTube parses out of a video description."""
    chapters = extract_chapters(project)
    with_hours = chapters[-1][0] >= 3600
    return "\n".join(
        f"{format_timestamp(seconds, with_hours)} {title}" for seconds, title in chapters
    )


def build_chapter_edl(
    project,
    record_start: str = DEFAULT_RECORD_START,
    fps: Optional[float] = None,
) -> str:
    """Chapters as a Resolve marker EDL, each marker running to the next chapter."""
    chapters = extract_chapters(project)

    if fps is None:
        source = project.get_artifact_path("original_file")
        fps = probe_fps(source) if Path(source).exists() else DEFAULT_FPS

    events = []
    for index, (start, title) in enumerate(chapters):
        is_last = index == len(chapters) - 1
        end = start + LAST_MARKER_SECONDS if is_last else chapters[index + 1][0]
        events.append((start, max(end, start), title, MARKER_COLOR))

    return build_marker_edl(
        events,
        fps=fps,
        title=f"{project.name} Chapters",
        record_start=record_start,
    )


class ChapterExporter:
    """On-demand service producing the chapter exports for a project."""

    def __init__(self, record_start: str = DEFAULT_RECORD_START):
        self.record_start = record_start

    def youtube(self, project) -> str:
        return build_youtube_chapters(project)

    def edl(self, project) -> str:
        return build_chapter_edl(project, record_start=self.record_start)
