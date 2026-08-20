"""Export project highlights as a CMX3600 EDL of timeline markers.

DaVinci Resolve imports these via Timeline > Import > Timeline Markers from EDL.
Each highlight becomes one event whose comment line carries the Resolve marker
fields: |C: colour, |M: name, |D: duration in frames.

Marker positions are record timecodes, so the EDL only lines up if the target
timeline starts at the same timecode used here (Resolve's default is
01:00:00:00, which is also the default of `record_start`).
"""

import logging
from pathlib import Path
from typing import List, Optional, Tuple

import cv2

from backend.src.dataclasses.data import Highlight

logger = logging.getLogger(__name__)

DEFAULT_FPS = 30.0
DEFAULT_RECORD_START = "01:00:00:00"
MARKER_COLOR = "ResolveColorBlue"
CLIP_GENERATED_MARKER_COLOR = "ResolveColorGreen"
MAX_MARKER_NAME = 80


def probe_fps(video_path: Path) -> float:
    """Read the frame rate of a video, falling back to DEFAULT_FPS."""
    capture = cv2.VideoCapture(str(video_path))
    fps = capture.get(cv2.CAP_PROP_FPS)
    capture.release()
    if not fps or fps <= 0:
        logger.warning(f"Could not read fps from {video_path}, using {DEFAULT_FPS}")
        return DEFAULT_FPS
    return float(fps)


def timebase(fps: float) -> int:
    """Integer timecode base for a real frame rate (29.97 -> 30, 23.976 -> 24)."""
    return max(1, int(round(fps)))


def frames_to_timecode(frames: int, base: int) -> str:
    """Format a frame count as non-drop-frame HH:MM:SS:FF."""
    frames = max(0, int(frames))
    seconds, ff = divmod(frames, base)
    minutes, ss = divmod(seconds, 60)
    hours, mm = divmod(minutes, 60)
    return f"{hours % 24:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


def timecode_to_frames(timecode: str, base: int) -> int:
    """Parse a non-drop-frame HH:MM:SS:FF timecode into a frame count."""
    parts = timecode.replace(';', ':').split(':')
    if len(parts) != 4:
        raise ValueError(f"Invalid timecode: {timecode}")
    hours, minutes, seconds, frames = (int(p) for p in parts)
    return ((hours * 60 + minutes) * 60 + seconds) * base + frames


def sanitize_marker_name(text: str) -> str:
    """Strip characters that would break the pipe-delimited comment line."""
    cleaned = " ".join(text.replace('|', '/').split())
    if len(cleaned) > MAX_MARKER_NAME:
        cleaned = cleaned[:MAX_MARKER_NAME - 1].rstrip() + "…"
    return cleaned


def marker_name(highlight: Highlight, index: int) -> str:
    text = highlight.viral_hook_text or highlight.highlight_text or f"Highlight {index + 1}"
    return sanitize_marker_name(text)


def build_marker_edl(
    events: List[Tuple[float, float, str, str]],
    fps: float = DEFAULT_FPS,
    title: str = "Markers",
    record_start: str = DEFAULT_RECORD_START,
    reel: str = "AX",
) -> str:
    """Render `(start, end, name, colour)` events as CMX3600 EDL marker text.

    Shared by the highlight and chapter exports; both differ only in how they
    derive those four values.
    """
    base = timebase(fps)
    offset = timecode_to_frames(record_start, base)

    lines = [f"TITLE: {sanitize_marker_name(title)}", "FCM: NON-DROP FRAME", ""]

    # EDL events must run ascending by record timecode; LLM output does not.
    event = 0
    for index, (start, end, name, color) in enumerate(sorted(events, key=lambda e: e[0])):
        start_frame = int(round(start * fps))
        duration = max(1, int(round(end * fps)) - start_frame)

        event += 1
        record_in = frames_to_timecode(offset + start_frame, base)
        record_out = frames_to_timecode(offset + start_frame + duration, base)
        source_in = frames_to_timecode(start_frame, base)
        source_out = frames_to_timecode(start_frame + duration, base)

        lines.append(
            f"{event:03d}  {reel:<8}V     C        "
            f"{source_in} {source_out} {record_in} {record_out}"
        )
        lines.append(f" |C:{color} |M:{sanitize_marker_name(name)} |D:{duration}")
        lines.append("")

    return "\n".join(lines)


def build_edl(
    highlights: List[Highlight],
    fps: float = DEFAULT_FPS,
    title: str = "Highlights",
    record_start: str = DEFAULT_RECORD_START,
    reel: str = "AX",
) -> str:
    """Render highlights as CMX3600 EDL text with Resolve marker comments."""
    events = []
    for index, highlight in enumerate(highlights):
        if highlight.end <= highlight.start:
            logger.warning(f"Skipping highlight {index} with empty range")
            continue
        color = CLIP_GENERATED_MARKER_COLOR if highlight.is_clip_generated else MARKER_COLOR
        events.append((highlight.start, highlight.end, marker_name(highlight, index), color))

    return build_marker_edl(events, fps=fps, title=title, record_start=record_start, reel=reel)


def build_project_edl(project, record_start: str = DEFAULT_RECORD_START, fps: Optional[float] = None) -> str:
    """Build the marker EDL for a project, probing the source video for fps."""
    if fps is None:
        source = project.get_artifact_path("original_file")
        fps = probe_fps(source) if Path(source).exists() else DEFAULT_FPS

    return build_edl(
        project.highlights,
        fps=fps,
        title=f"{project.name} Highlights",
        record_start=record_start,
    )


class MarkerExporter:
    """On-demand service producing the highlight marker EDL for a project.

    Not part of the pipeline: the UI calls it directly through the API.
    """

    def __init__(self, record_start: str = DEFAULT_RECORD_START):
        self.record_start = record_start

    def render(self, project) -> str:
        """Returns the EDL text for the project's highlights."""
        logger.info(f"MarkerExporter rendering project={project.project_id}, highlight_count={len(project.highlights)}")
        return build_project_edl(project, record_start=self.record_start)

    def export(self, project) -> Path:
        """Writes markers.edl into the project directory and returns its path."""
        path = project.get_artifact_path("marker_file")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.render(project), encoding="utf-8")
        logger.info(f"MarkerExporter wrote {path}")
        return path
