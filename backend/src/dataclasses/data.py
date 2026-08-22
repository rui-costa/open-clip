from dataclasses import dataclass, asdict, field
from typing import Callable, List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
import json
import csv
import logging
import os
import threading

logger = logging.getLogger(__name__)

# One lock per project id, so writes from concurrently running steps serialize
# instead of overwriting each other.
_METADATA_LOCKS: Dict[str, threading.RLock] = {}
_METADATA_LOCKS_GUARD = threading.Lock()


def _metadata_lock(project_id: str) -> threading.RLock:
    with _METADATA_LOCKS_GUARD:
        lock = _METADATA_LOCKS.get(project_id)
        if lock is None:
            lock = threading.RLock()
            _METADATA_LOCKS[project_id] = lock
        return lock

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
    marker_file: str = "markers.edl"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

# ... inside Project class ...

@dataclass
class Highlights:
    items: List[Dict[str, Any]]
    total_highlights: int = 0
    total_clips: int = 0

    def __post_init__(self):
        self.highlights = []
        for index, item in enumerate(self.items):
            if not isinstance(item, dict):
                logger.warning(f"Dropping highlight {index}: not an object")
                continue
            h = Highlight.from_json(item)
            if h.end <= h.start:
                logger.warning(
                    f"Dropping highlight {index} with unusable range "
                    f"start={item.get('start')!r} end={item.get('end')!r}"
                )
                continue
            self.highlights.append(h)
        self.total_highlights = len(self.highlights)
        self.total_clips = len([h for h in self.highlights if h.is_clip_generated])

def _as_seconds(value: Any) -> float:
    """Coerces an LLM- or file-supplied timestamp to non-negative seconds.

    Anything unreadable becomes 0.0, which `Highlights` then drops as an empty
    range rather than cutting a clip at the top of the video.
    """
    if isinstance(value, bool) or value is None:
        return 0.0
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        logger.warning(f"Unreadable highlight timestamp {value!r}")
        return 0.0
    if seconds != seconds or seconds in (float("inf"), float("-inf")):
        return 0.0
    return max(0.0, seconds)


def _bounded(value: Any, low: float, high: float, fallback: float) -> float:
    """Coerces a user- or file-supplied number into `[low, high]`.

    Overlay numbers reach an ASS file and inline CSS, so anything unreadable
    falls back rather than propagating a NaN into either renderer.
    """
    if isinstance(value, bool) or value is None:
        return fallback
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if number != number or number in (float("inf"), float("-inf")):
        return fallback
    return max(low, min(high, number))


def _hex_color(value: Any, fallback: Optional[str]) -> Optional[str]:
    """Accepts `#RGB`, `#RRGGBB` or `#RRGGBBAA`; anything else keeps `fallback`.

    None passes through, which is what "no background block" means.
    """
    if value is None:
        return None
    if not isinstance(value, str) or not value.startswith("#"):
        return fallback
    digits = value.strip()[1:]
    if len(digits) not in (3, 6, 8) or any(c not in "0123456789abcdefABCDEF" for c in digits):
        return fallback
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return f"#{digits.upper()}"


@dataclass
class OverlayText:
    """A title drawn over one clip for the first few seconds, then faded out.

    Separate from captions on purpose: captions are the spoken words, timed by
    the word map and styled per project, while this is one piece of text the
    user writes for one clip. They share a renderer — both end up as events in
    the same ASS file — but nothing else.

    Sizes are percentages of the output frame, like a caption style, so the
    browser preview and the burned render draw the same thing at different
    sizes. Times are seconds from the start of the clip, not from the start of
    the source video.
    """

    enabled: bool = False
    text: str = ""
    # Defaulted to the top of the clip because that is what a title is for; the
    # field exists so a user who wants it later is not blocked.
    start: float = 0.0
    duration: float = 3.0
    # No fade in by default: a title is meant to be readable on the first frame,
    # and a clip whose opening second is spent ramping one up has thrown that
    # frame away. It is a field rather than a constant so a fade can be asked
    # for; it is simply not assumed.
    fade_in: float = 0.0
    fade_out: float = 0.6
    font_family: str = "Arial Black"
    # Thumbnail guidance says as large as possible, and the frame says how
    # large that is: libass wraps at spaces but cannot break a word, so a title
    # sized past what its longest word can fit is a word cut off at the frame
    # edge. Eight percent of a 1080x1920 short holds about eight uppercase
    # characters a line in Arial Black, which most hooks clear. Anything longer
    # is a size decision on that clip, and the editor says when one is due.
    font_size_pct: float = 8.0
    bold: bool = True
    italic: bool = False
    uppercase: bool = True
    text_color: str = "#FFFFFF"
    outline_color: str = "#000000"
    # Toward the heavy end of the 4-8px advised for a 720-high still, because a
    # video frame is the busy background the same guidance says to go heavier
    # on: whatever is behind these words is moving footage, never a flat colour.
    outline_pct: float = 0.9
    # A hard offset shadow, drawn down and right with no blur, the way the
    # caption style's is. It is what makes a title read as sitting *over* the
    # picture rather than printed onto it — and, unlike a fade or a scale-up,
    # it is still there in one frame. That matters because this same object is
    # drawn on the thumbnail, which is a single frame and has no motion to
    # show: any pop that depends on time is a pop the thumbnail never gets.
    shadow_color: str = "#000000"
    shadow_pct: float = 0.8
    # One word in a second colour is what a thumbnail that gets clicked does:
    # the eye lands on the marked word and reads out from it. The user marks it
    # by wrapping it in asterisks, so the mark lives in the text they already
    # type rather than in a second field they have to keep in step with it. A
    # title with no asterisks in it is drawn exactly as before.
    highlight_color: str = "#FFE000"
    box_color: Optional[str] = None
    # Distance from the *top* of the frame to the top of the text. Captions
    # measure from the bottom because that is where captions live; a title is
    # placed from the edge it hangs off.
    position_pct: float = 12.0
    max_width_pct: float = 86.0

    @property
    def end(self) -> float:
        return self.start + self.duration

    def is_visible(self) -> bool:
        """Whether this would actually draw anything."""
        return bool(self.enabled and self.text.strip() and self.duration > 0)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> 'OverlayText':
        if not isinstance(data, dict):
            return cls()
        defaults = cls()
        return cls(
            enabled=bool(data.get("enabled", False)),
            # Trimmed of nothing: leading spaces are the user's business. Only
            # the length is capped, because this is drawn on a video frame.
            text=str(data.get("text") or "")[:200],
            start=_bounded(data.get("start", defaults.start), 0.0, 3600.0, defaults.start),
            duration=_bounded(data.get("duration", defaults.duration), 0.1, 600.0, defaults.duration),
            fade_in=_bounded(data.get("fade_in", defaults.fade_in), 0.0, 10.0, defaults.fade_in),
            fade_out=_bounded(data.get("fade_out", defaults.fade_out), 0.0, 10.0, defaults.fade_out),
            font_family=str(data.get("font_family") or defaults.font_family)[:100],
            font_size_pct=_bounded(data.get("font_size_pct", defaults.font_size_pct), 1.0, 25.0, defaults.font_size_pct),
            bold=bool(data.get("bold", defaults.bold)),
            italic=bool(data.get("italic", defaults.italic)),
            uppercase=bool(data.get("uppercase", defaults.uppercase)),
            text_color=_hex_color(data.get("text_color"), defaults.text_color) or defaults.text_color,
            outline_color=_hex_color(data.get("outline_color"), defaults.outline_color) or defaults.outline_color,
            outline_pct=_bounded(data.get("outline_pct", defaults.outline_pct), 0.0, 3.0, defaults.outline_pct),
            shadow_color=_hex_color(data.get("shadow_color"), defaults.shadow_color) or defaults.shadow_color,
            shadow_pct=_bounded(data.get("shadow_pct", defaults.shadow_pct), 0.0, 3.0, defaults.shadow_pct),
            highlight_color=_hex_color(data.get("highlight_color"), defaults.highlight_color) or defaults.highlight_color,
            box_color=_hex_color(data.get("box_color"), defaults.box_color),
            position_pct=_bounded(data.get("position_pct", defaults.position_pct), 0.0, 100.0, defaults.position_pct),
            max_width_pct=_bounded(data.get("max_width_pct", defaults.max_width_pct), 10.0, 100.0, defaults.max_width_pct),
        )


@dataclass
class ThumbnailSettings:
    """The still picture that stands for one clip, and how it is built.

    Every field has a default that produces something publishable without the
    user touching anything: the first frame of the clip, no subtitles, and the
    clip's own title drawn over it. That is the whole point of the defaults —
    a clip that is never opened still gets a thumbnail, and the settings here
    only describe departures from it.

    `frame_time` is seconds from the start of the clip, like an overlay's
    times, not a position in the source video. `extra` is a second piece of
    text the user adds for the thumbnail alone; it never reaches the video.
    """

    frame_time: float = 0.0
    # Off by default: a caption caught mid-sentence is the one thing a
    # thumbnail does not need, and the words are legible in the video itself.
    show_captions: bool = False
    show_overlay: bool = True
    extra: Optional[OverlayText] = None
    # What the last render produced, or None while none has been made. The
    # filename does not change between renders, so `generated_at` is what a
    # browser holding the previous image is told about the new one.
    generated_filename: Optional[str] = None
    generated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["extra"] = self.extra.to_dict() if self.extra else None
        return data

    @classmethod
    def from_dict(cls, data: Any) -> 'ThumbnailSettings':
        if not isinstance(data, dict):
            return cls()
        defaults = cls()
        extra = data.get("extra")
        return cls(
            # An hour is well past any short; the clip's own length bounds it
            # again at render time, where the duration is actually known.
            frame_time=_bounded(data.get("frame_time", defaults.frame_time), 0.0, 3600.0, defaults.frame_time),
            show_captions=bool(data.get("show_captions", defaults.show_captions)),
            show_overlay=bool(data.get("show_overlay", defaults.show_overlay)),
            extra=OverlayText.from_dict(extra) if isinstance(extra, dict) else None,
            generated_filename=data.get("generated_filename") or None,
            generated_at=data.get("generated_at") or None,
        )


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
    # The model's description of this short on its own. It carries no link and
    # no boilerplate: the sentence pointing back at the source video and any
    # standing text come from the description template, which is the user's to
    # edit. Defaulted because it sits after `start`/`end` and because every
    # highlight produced before this field existed simply has none.
    video_description_for_youtube_short: str = ""
    # The words for the still image, which is the thing anyone decides to click
    # on. Separate from `viral_hook_text` because the two are read under
    # different conditions: the hook is laid over the opening seconds of a video
    # that is already playing, while this is read at about 120 pixels wide in a
    # feed, with no sound and no context. That makes it shorter, blunter, and
    # carrying one word marked with asterisks for the renderer to colour.
    # Defaulted because every highlight produced before this field existed has
    # none, and the thumbnail falls back to the hook for those.
    thumbnail_text: str = ""
    is_clip_generated: bool = False
    generated_clip_filename: Optional[str] = None
    # What a YouTube upload of this clip produced, or None while it has never
    # been published. Kept per highlight rather than in a project-level list
    # because publishing is irreversible from here: the clip page has to be able
    # to say "this one is already live" before the user clicks again.
    youtube_video_id: Optional[str] = None
    youtube_url: Optional[str] = None
    uploaded_at: Optional[str] = None
    # Why the last publish attempt did not produce a video, or None when the
    # last attempt worked or none has been made. Publishing runs in the
    # background — it re-cuts the clip first, which outlives a browser request —
    # so the sentence the user needs cannot be the response to their click; it
    # is written here and read back when the job leaves /active_processes.
    upload_error: Optional[str] = None
    # Whether the rendered file has captions in its pixels. The preview overlay
    # keys off this: drawing captions over a clip that already has them burned
    # in would show every word twice.
    captions_burned: bool = False
    # Caption settings belonging to this clip alone, or None to follow the
    # project. None is the locked state: the clip has no opinion and inherits
    # whatever the project currently says, including later changes to it.
    # Storing None rather than a copy is what makes that inheritance live.
    captions: Optional[CaptionSettings] = None
    # The title drawn over this clip, or None for a clip that has never had one.
    # Per clip rather than per project: it is text about this moment.
    overlay: Optional[OverlayText] = None
    # Whether the rendered file already has the overlay in its pixels, the same
    # promise `captions_burned` makes about the captions. The preview draws the
    # overlay only while this is false, so a re-render does not show it twice.
    overlay_burned: bool = False
    # When the file on disk was last written. The filename does not change
    # between renders, so this is what a browser cache is busted with after a
    # clip is regenerated.
    rendered_at: Optional[str] = None
    # How this clip's thumbnail is built, or None for a clip nobody has chosen
    # a frame for. None is not "no thumbnail": it means the defaults, which is
    # exactly what a thumbnail rendered without any input uses.
    thumbnail: Optional[ThumbnailSettings] = None

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        # asdict turns a None dataclass field into None and a present one into
        # a plain dict, which is exactly the shape from_json reads back.
        data["captions"] = self.captions.to_dict() if self.captions else None
        data["overlay"] = self.overlay.to_dict() if self.overlay else None
        data["thumbnail"] = self.thumbnail.to_dict() if self.thumbnail else None
        return data

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'Highlight':
        """Builds a Highlight from stored or LLM-returned JSON.

        `start`/`end` are taken verbatim from the payload. The highlights prompt
        picks them straight out of the word map and the schema requires them, so
        there is no text-matching step: a clip and its EDL marker are always cut
        from the same two numbers, whenever either is produced.
        """
        return cls(
            highlight_text=data.get("highlight_text", ""),
            viral_hook_text=data.get("viral_hook_text", ""),
            video_description_for_x=data.get("video_description_for_x", ""),
            video_description_for_reddit=data.get("video_description_for_reddit", ""),
            video_description_for_linkedin=data.get("video_description_for_linkedin", ""),
            video_title_for_youtube_short=data.get("video_title_for_youtube_short", ""),
            video_description_for_youtube_short=data.get("video_description_for_youtube_short", ""),
            thumbnail_text=data.get("thumbnail_text", ""),
            start=_as_seconds(data.get("start")),
            end=_as_seconds(data.get("end")),
            is_clip_generated=data.get("is_clip_generated", False),
            generated_clip_filename=data.get("generated_clip_filename"),
            youtube_video_id=data.get("youtube_video_id"),
            youtube_url=data.get("youtube_url"),
            uploaded_at=data.get("uploaded_at"),
            upload_error=data.get("upload_error"),
            # Clips cut before captions existed have none burned in, which is
            # exactly what the default says.
            captions_burned=data.get("captions_burned", False),
            # Absent or null means locked to the project, which is what every
            # highlight written before this field existed will say.
            captions=(
                CaptionSettings.from_dict(data["captions"])
                if isinstance(data.get("captions"), dict)
                else None
            ),
            # Absent for every clip that has never been given a title, which is
            # every clip written before this field existed.
            overlay=(
                OverlayText.from_dict(data["overlay"])
                if isinstance(data.get("overlay"), dict)
                else None
            ),
            overlay_burned=data.get("overlay_burned", False),
            rendered_at=data.get("rendered_at"),
            # Absent for every clip whose thumbnail has never been touched,
            # which reads as "the defaults" rather than as "none".
            thumbnail=(
                ThumbnailSettings.from_dict(data["thumbnail"])
                if isinstance(data.get("thumbnail"), dict)
                else None
            ),
        )

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
        """Builds the stored shape from whatever the metadata prompt returned.

        The prompt returns one overall `summary`, a flat list of `titles`, and a
        `top_2` list referring back to those titles by index. Older prompts
        returned `components`/`top_recommendations` with the summary and reason
        repeated on every item, so both are accepted.
        """
        if isinstance(data, list):
            data = {"components": data}

        items = data.get("components") or data.get("titles") or []
        recommendations = data.get("top_recommendations") or data.get("top_2") or []

        # The reason lives on the recommendation, not on the title it points at.
        reasons: Dict[int, str] = {}
        for entry in recommendations:
            if isinstance(entry, dict) and isinstance(entry.get("index"), int):
                reasons[entry["index"]] = str(entry.get("reason", ""))

        overall_summary = str(data.get("summary", ""))
        components = []
        for position, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            index = item.get("index")
            if not isinstance(index, int) or isinstance(index, bool):
                index = position
            components.append(VideoComponent(
                index=index,
                title=str(item.get("title", "")),
                summary=str(item.get("summary") or overall_summary),
                post_for_x=str(item.get("post_for_x", "")),
                post_for_reddit=str(item.get("post_for_reddit", "")),
                post_for_linkedin=str(item.get("post_for_linkedin", "")),
                reason=str(item.get("reason") or reasons.get(index, "")),
            ))

        return cls(components=components, top_recommendations=list(recommendations))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "components": [c.to_dict() for c in self.components],
            "top_recommendations": self.top_recommendations
        }

@dataclass
class CaptionSettings:
    """Per-project caption choice: a named preset plus any tweaks on top of it.

    Only the preset name and the fields the user actually changed are stored.
    Keeping overrides sparse means a preset can be improved in config and every
    project that did not deliberately override that field picks the change up.
    """
    enabled: bool = False
    preset: str = "karaoke_pop"
    overrides: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> 'CaptionSettings':
        if not isinstance(data, dict):
            return cls()
        overrides = data.get("overrides")
        return cls(
            enabled=bool(data.get("enabled", False)),
            preset=str(data.get("preset") or "karaoke_pop"),
            overrides=dict(overrides) if isinstance(overrides, dict) else {},
        )


@dataclass
class DescriptionSettings:
    """What this project contributes to the YouTube description of its clips.

    `source_url` is the full episode the shorts were cut from. It becomes a
    link in the description of every clip, so it is a project fact rather than
    something the model can invent, and `source_title` is how the episode is
    named in prose. It is not YouTube's "Related video" chip: that has no field
    in the Data API and is set per short in Studio.

    `text` is the project's standing text — a call to action, links, credits —
    and `template` overrides the application-wide description template for this
    project alone. Both are empty by default, meaning "use the global one".
    """
    source_url: str = ""
    source_title: str = ""
    text: str = ""
    template: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Any) -> 'DescriptionSettings':
        if not isinstance(data, dict):
            return cls()
        return cls(
            source_url=str(data.get("source_url") or ""),
            source_title=str(data.get("source_title") or ""),
            text=str(data.get("text") or ""),
            template=str(data.get("template") or ""),
        )


# What a clip shows while it is sitting still: its thumbnail, or the video
# frame it is parked on. A project chooses once for all of its clips, because
# the choice is about how the project is reviewed rather than about one clip.
CLIP_PREVIEW_CHOICES = ("thumbnail", "video")


@dataclass
class ProjectSettings:
    aspect_ratio: str
    resolution: str
    captions: CaptionSettings = field(default_factory=CaptionSettings)
    # How a title is drawn across this project — font, size, placement,
    # colours, timing — and nothing about what it says. The words belong to the
    # clip: they are the one thing about a title that cannot be the same on
    # every short, whether the user typed them or the model wrote them. `text`
    # is carried only because this is an `OverlayText` and is held empty.
    #
    # Default-constructed rather than optional, so a project always has a look
    # to draw with; switched off, so a project nobody has touched burns nothing
    # into its clips.
    overlay: OverlayText = field(default_factory=OverlayText)
    description: DescriptionSettings = field(default_factory=DescriptionSettings)
    # Thumbnail by default: a grid of stills is what the shorts will look like
    # in a feed, which is the question being asked while reviewing them. The
    # video frame is one click away either way.
    clip_preview: str = "thumbnail"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectSettings':
        """Builds settings from stored metadata, ignoring keys it does not own.

        Projects created before a settings field existed simply do not carry it,
        so every field other than the two originals has a default.
        """
        preview = data.get("clip_preview")
        return cls(
            aspect_ratio=data.get("aspect_ratio", "keep original"),
            resolution=data.get("resolution", "keep original"),
            captions=CaptionSettings.from_dict(data.get("captions")),
            # Text stripped on the way in as well as on the way out: a project
            # saved before this was configuration-only carries a line that
            # would otherwise reappear over every clip at once.
            overlay=OverlayText.from_dict({**(data.get("overlay") or {}), "text": ""}),
            description=DescriptionSettings.from_dict(data.get("description")),
            # Anything else — a typo, a value from a later version — reads as
            # the default rather than reaching the page as a state it cannot
            # draw.
            clip_preview=preview if preview in CLIP_PREVIEW_CHOICES else "thumbnail",
        )

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
    # Output of config-driven LLM tasks that have no typed field of their own,
    # keyed by task name.
    llm_outputs: Dict[str, Any] = field(default_factory=dict)
    settings: ProjectSettings = field(default_factory=lambda: ProjectSettings("16:9", "1080p"))
    status: Optional[str] = None
    step_statuses: Dict[str, str] = field(default_factory=dict)
    base_path: Path = field(default=Path("projects"))
    base_directory: str = "projects"
    clip_base_directory: str = "clips"
    _word_map: Optional[WordMap] = field(default=None, init=False, repr=False)

    def get_artifact_path(self, key: str) -> Path:
        base = self.base_path / (self.project_id or "")
        return base / getattr(self.files, key)

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

    def metadata_path(self) -> Path:
        return Path(self.base_directory) / self.project_id / "metadata.json"

    def _write_metadata(self, data: Dict[str, Any]):
        path = self.metadata_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Written to a temporary file and swapped in, so a concurrent reader
        # never sees a half-written metadata.json.
        tmp = path.with_name(f"{path.name}.tmp")
        with open(tmp, 'w') as f:
            json.dump(data, f, indent=4)
        os.replace(tmp, path)

    def _read_metadata(self) -> Dict[str, Any]:
        path = self.metadata_path()
        if not path.exists():
            return self.to_dict()
        with open(path, 'r') as f:
            return json.load(f)

    def _mutate_metadata(self, mutate: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
        """Applies a change to metadata.json without rewriting the whole file.

        Pipeline steps run concurrently, each holding the Project snapshot it
        loaded when it started. A full save from one step would roll back
        everything the others wrote after that snapshot was taken, which is how
        a completed step could reappear as running and its output vanish.
        """
        with _metadata_lock(self.project_id):
            data = self._read_metadata()
            mutate(data)
            self._write_metadata(data)
            return data

    def save(self):
        """Writes this snapshot in full. Only safe when nothing else is running."""
        with _metadata_lock(self.project_id):
            self._write_metadata(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "files": self.files.to_dict(),
            "highlights": [h.to_dict() for h in self.highlights],
            "video_metadata": self.video_metadata.to_dict(),
            "llm_outputs": self.llm_outputs,
            "settings": self.settings.to_dict(),
            "status": self.status,
            "step_statuses": self.step_statuses
        }

    def from_dict(self, metadata: Dict[str, Any]):
        self.project_id = metadata["project_id"]
        self.name = metadata["name"]
        self.created_at = datetime.fromisoformat(metadata["created_at"])
        self.files = ProjectFileSettings(**metadata["files"])
        self.highlights = [Highlight.from_json(h) for h in metadata["highlights"]]

        comp = [VideoComponent(**c) for c in metadata["video_metadata"]["components"]]
        self.video_metadata = VideoMetadata(comp, metadata["video_metadata"]["top_recommendations"])

        self.llm_outputs = metadata.get("llm_outputs", {})

        self.settings = ProjectSettings.from_dict(metadata.get("settings") or {})
        
        self.status = metadata.get("status")
        self.step_statuses = metadata.get("step_statuses", {})

    def set_step_status(self, step: str, status: str):
        def mutate(data: Dict[str, Any]):
            statuses = data.get("step_statuses") or {}
            statuses[step] = status
            data["step_statuses"] = statuses

        # Only this step's entry is touched; the statuses of steps running in
        # parallel are read back from disk rather than from a stale snapshot.
        self.step_statuses = self._mutate_metadata(mutate)["step_statuses"]

    def set_property(self, key: str, value: Any):
        setattr(self, key, value)
        serialized = self.to_dict()
        payload = serialized[key] if key in serialized else value
        self._mutate_metadata(lambda data: data.__setitem__(key, payload))

    def set_llm_output(self, task: str, value: Any):
        """Stores the output of an LLM task that has no typed field of its own."""
        def mutate(data: Dict[str, Any]):
            outputs = data.get("llm_outputs") or {}
            outputs[task] = value
            data["llm_outputs"] = outputs

        self.llm_outputs = self._mutate_metadata(mutate)["llm_outputs"]

    def clear_llm_output(self, task: str):
        def mutate(data: Dict[str, Any]):
            outputs = data.get("llm_outputs") or {}
            outputs.pop(task, None)
            data["llm_outputs"] = outputs

        self.llm_outputs = self._mutate_metadata(mutate)["llm_outputs"]

    def delete_highlight(self, index: int):
        """Removes the highlight at `index` along with any clip cut from it.

        `index` is a position in `highlights`, which is exactly what the clip
        grid renders: every highlight is a card from the moment the highlights
        step finishes, whether or not a clip has been rendered for it yet.

        The highlight is dropped outright rather than just losing its clip, so
        it also stops appearing in the marker and chapter exports.

        Raises IndexError when no highlight exists at that position.
        """
        removed: Dict[str, Any] = {}

        def mutate(data: Dict[str, Any]):
            highlights = data.get("highlights", [])
            if index < 0 or index >= len(highlights):
                raise IndexError(f"No highlight at index {index}")
            removed["filename"] = highlights[index].get("generated_clip_filename")
            thumbnail = highlights[index].get("thumbnail")
            if isinstance(thumbnail, dict):
                removed["thumbnail"] = thumbnail.get("generated_filename")
            del highlights[index]
            data["highlights"] = highlights

        self._mutate_metadata(mutate)

        # metadata.json is what the grid renders, so the file is unlinked only
        # after the entry is gone: a failed unlink must not leave behind a clip
        # the UI still lists but cannot play. `missing_ok` covers the file
        # already being gone, which is not a reason to fail the request.
        filename = removed.get("filename")
        if filename:
            Path(self.get_clip_path(filename)).unlink(missing_ok=True)

        # The still goes with the clip it stood for, by the same rule: the
        # entry is gone from metadata.json first, so a failed unlink cannot
        # leave a picture the UI still lists. The directory is named here
        # rather than imported from Thumbnailer, which imports this module.
        thumbnail = removed.get("thumbnail")
        if thumbnail:
            (Path(self.base_directory) / self.project_id / "thumbnails" / thumbnail).unlink(missing_ok=True)

        if index < len(self.highlights):
            del self.highlights[index]