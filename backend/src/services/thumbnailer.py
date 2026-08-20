"""Build the still picture that stands for a clip.

A thumbnail here is a frame of the clip with text drawn on it, produced by the
same pipeline the video is: the same crop, the same styles, the same font
files, burned by libass through ffmpeg. That is the point — a thumbnail made
some other way looks like a different video than the one it opens.

The defaults are what a user who does nothing gets: the first frame of the
clip, no subtitles, and the clip's title over it. Everything in
`ThumbnailSettings` is a departure from that.
"""

import logging
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.src.dataclasses.data import Highlight, OverlayText, Project, ThumbnailSettings
from backend.src.infrastructure.video_engine import OpenCVVideoEngine
from backend.src.services.ass_writer import render_still_ass
from backend.src.services.captions import CaptionService

logger = logging.getLogger(__name__)


class SourceVideoMissingError(Exception):
    """There is no source video to take a frame out of."""


class Thumbnailer:
    """Renders and stores one thumbnail per clip."""

    # Beside clips/ rather than inside it: the clip directory is emptied every
    # time the clipper starts, and a thumbnail outlives a re-cut.
    DIRECTORY = "thumbnails"

    def __init__(self, caption_service: Optional[CaptionService] = None):
        self.captions = caption_service or CaptionService()

    def settings(self, highlight: Highlight) -> ThumbnailSettings:
        """This clip's thumbnail settings, or the defaults it has never left."""
        stored = getattr(highlight, "thumbnail", None)
        return stored if stored is not None else ThumbnailSettings()

    def title(self, highlight: Highlight) -> Optional[OverlayText]:
        """The text drawn over the still, worked out rather than asked for.

        The clip's own title first: a clip whose opening frames say one thing
        must not have a thumbnail saying another. Failing that, the hook the
        model wrote for this moment, then the YouTube title — a thumbnail with
        no words on it is the one outcome worth avoiding.

        The stored title is used even when it is switched off for the video.
        `enabled` there answers "burn this into the clip"; whether the
        thumbnail carries text is `show_overlay`'s question, and a user who
        wrote a line and chose not to burn it still wrote the line.
        """
        stored = getattr(highlight, "overlay", None)
        if stored is not None and stored.text.strip():
            return stored

        text = (
            highlight.viral_hook_text
            or highlight.video_title_for_youtube_short
            or ""
        ).strip()
        if not text:
            return None
        # A fresh OverlayText, so an automatic title looks like the default a
        # user would have got had they typed it themselves.
        return OverlayText(enabled=True, text=text[:200])

    def overlays(self, highlight: Highlight, settings: ThumbnailSettings) -> List[OverlayText]:
        """Everything with words in it, bottom layer first."""
        drawn: List[OverlayText] = []
        if settings.show_overlay:
            title = self.title(highlight)
            if title is not None:
                drawn.append(title)
        # The extra line is the user's alone and has no `enabled` to consult:
        # it exists on the thumbnail because they added it there.
        if settings.extra is not None and settings.extra.text.strip():
            drawn.append(settings.extra)
        return drawn

    def frame_time(self, highlight: Highlight, settings: ThumbnailSettings) -> float:
        """The chosen moment, clamped inside the clip.

        A frame asked for past the end of the clip would come back as whatever
        the source happens to show there — the next speaker, the next scene —
        which is not a frame of this clip at all.
        """
        duration = max(0.0, float(highlight.end) - float(highlight.start))
        if duration <= 0:
            return 0.0
        # Backed off the very end, where seeking lands past the last frame.
        return max(0.0, min(settings.frame_time, max(0.0, duration - 0.05)))

    def directory(self, project: Project) -> Path:
        return Path(project.base_directory) / project.project_id / self.DIRECTORY

    def path(self, project: Project, highlight: Highlight) -> Optional[Path]:
        """Where this clip's rendered thumbnail is, or None if there is none."""
        settings = self.settings(highlight)
        if not settings.generated_filename:
            return None
        return self.directory(project) / settings.generated_filename

    def _write_ass(self, project: Project, highlight: Highlight, settings: ThumbnailSettings,
                   index: int, width: int, height: int, at: float) -> Optional[str]:
        """Writes the frozen subtitle script for one still, or nothing to draw.

        Written to a temporary file, not into the project: this is scratch for
        one ffmpeg run and nothing reads it afterwards. The clip's own `.ass`
        is a different thing — that one is the burn, and it is offered as a
        download for use in an editor.

        A caption failure costs the text, not the picture: a thumbnail of the
        frame alone is still a thumbnail, so this degrades rather than raising.
        """
        overlays = self.overlays(highlight, settings)
        cues: List[Any] = []
        if settings.show_captions:
            try:
                cues = self.captions.cues(project, highlight)
            except Exception as e:
                logger.error(f"Could not build thumbnail captions for clip {index}: {e}")

        if not overlays and not cues:
            return None

        try:
            style = self.captions.style(project, highlight)
            handle = tempfile.NamedTemporaryFile(
                mode="w", suffix=".ass", prefix=f"openclip_thumb_{index:03d}_",
                encoding="utf-8", delete=False,
            )
            with handle as scratch:
                scratch.write(render_still_ass(cues, style, width, height, overlays, at))
        except Exception as e:
            logger.error(f"Could not write thumbnail overlay for clip {index}: {e}")
            return None
        # Absolute: it is going into an ffmpeg filter argument, which is
        # resolved against the working directory of the encode, not this one.
        return str(Path(handle.name).resolve())

    def generate(self, project: Project, index: int, engine: Optional[Any] = None) -> ThumbnailSettings:
        """Renders this clip's thumbnail and records it on the highlight.

        Raises IndexError when there is no highlight at `index`, and
        SourceVideoMissingError when the video it would be cut from is gone.
        """
        if index < 0 or index >= len(project.highlights):
            raise IndexError(f"No highlight at index {index}")

        highlight = project.highlights[index]
        input_path = Path(project.get_artifact_path("original_file"))
        if not input_path.exists():
            raise SourceVideoMissingError(
                "The source video for this project is missing, so no frame can be taken from it."
            )

        settings = self.settings(highlight)
        engine = engine or OpenCVVideoEngine("root/yolov8n.pt")
        width, height = engine.resolve_output_dimensions(
            str(input_path), project.settings.aspect_ratio, project.settings.resolution
        )

        at = self.frame_time(highlight, settings)
        subtitle_path = self._write_ass(project, highlight, settings, index, width, height, at)

        filename = f"clip_{index:03d}.jpg"
        output_path = self.directory(project) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            engine.extract_frame(
                str(input_path),
                str(output_path.resolve()),
                float(highlight.start) + at,
                project.settings.aspect_ratio,
                project.settings.resolution,
                subtitle_path=subtitle_path,
                # Framed on the start of the clip, which is where the clip
                # itself is cropped: a thumbnail centred on a different moment
                # would show a different part of the frame than the video it
                # belongs to.
                framing_timestamp=float(highlight.start),
            )
        finally:
            # The script has done its one job. Kept even on failure would mean a
            # temp file per attempt, none of which anything reads again.
            if subtitle_path:
                Path(subtitle_path).unlink(missing_ok=True)
            # An earlier version wrote this beside the picture, where it was
            # never anything but litter in the user's project.
            (self.directory(project) / f"clip_{index:03d}.ass").unlink(missing_ok=True)

        settings.generated_filename = filename
        settings.generated_at = datetime.now().isoformat()
        highlight.thumbnail = settings
        project.set_property("highlights", project.highlights)
        logger.info(f"Wrote thumbnail for clip {index} at {at}s into the clip")
        return settings

    def preview(self, project: Project, highlight: Highlight) -> Dict[str, Any]:
        """What the browser needs to draw this thumbnail before it is rendered.

        The automatic title travels with it, because the page cannot work out
        for itself which of the model's fields would have been used.
        """
        settings = self.settings(highlight)
        title = self.title(highlight)
        return {
            "settings": settings.to_dict(),
            # Named `title` rather than `overlay`: this is the resolved text,
            # which may have come from the clip's title or from the model.
            "title": title.to_dict() if title is not None else None,
            "title_font": (
                self.captions.font({
                    "font_family": title.font_family,
                    "bold": title.bold,
                    "italic": title.italic,
                })
                if title is not None
                else None
            ),
            "duration": max(0.0, float(highlight.end) - float(highlight.start)),
        }
