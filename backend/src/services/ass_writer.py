"""Render caption cues as an ASS subtitle file for burning into a clip.

ffmpeg's `subtitles` filter draws this through libass, so the burned result is
whatever libass makes of these lines. The percentages in a caption style are
resolved against the *output* frame here, which is why the writer needs the
target width and height rather than the source ones.

Per-word animation is done with one event per word rather than with `\\k`
karaoke tags: `\\k` only fills a colour left to right on a fixed line, while an
event per word can also scale the spoken word, and behaves the same across
libass versions.
"""

import logging
from typing import Any, Dict, List, Optional, Sequence

from backend.src.dataclasses.data import OverlayText
from backend.src.infrastructure.font_metrics import face_for_style, resolve_face
from backend.src.services.caption_builder import CaptionCue

logger = logging.getLogger(__name__)

# Everything downstream is written against this style name.
STYLE_NAME = "OpenClip"

# The overlay title gets a style of its own rather than sharing the caption
# one: it is anchored to the top of the frame, in the user's own words, and
# has to keep its look when captions are switched off entirely.
OVERLAY_STYLE_NAME = "OpenClipOverlay"


def _hex_parts(color: str) -> tuple:
    """Splits `#RRGGBB` / `#RRGGBBAA` into (r, g, b, alpha), alpha 0-255 opaque-first."""
    digits = color.lstrip("#")
    red, green, blue = (int(digits[i:i + 2], 16) for i in (0, 2, 4))
    alpha = int(digits[6:8], 16) if len(digits) == 8 else 255
    return red, green, blue, alpha


def ass_color(color: str, force_opaque: bool = False) -> str:
    """CSS hex to the ASS `&HAABBGGRR&` form, where AA is *transparency*."""
    red, green, blue, alpha = _hex_parts(color)
    transparency = 0 if force_opaque else 255 - alpha
    return f"&H{transparency:02X}{blue:02X}{green:02X}{red:02X}"


def ass_timestamp(seconds: float) -> str:
    """Seconds as ASS `H:MM:SS.cc`."""
    total = max(0.0, float(seconds))
    hours, remainder = divmod(int(total), 3600)
    minutes, whole_seconds = divmod(remainder, 60)
    centiseconds = int(round((total - int(total)) * 100))
    if centiseconds >= 100:
        centiseconds = 99
    return f"{hours:d}:{minutes:02d}:{whole_seconds:02d}.{centiseconds:02d}"


def escape_text(text: str) -> str:
    """Neutralises the characters that would otherwise be read as ASS markup."""
    return (
        text.replace("\\", "\\\\")
        .replace("{", "(")
        .replace("}", ")")
        .replace("\n", " ")
        .replace("\r", " ")
    )


def _word_text(word_text: str, style: Dict[str, Any]) -> str:
    return escape_text(word_text.upper() if style["uppercase"] else word_text)


def build_style_line(style: Dict[str, Any], width: int, height: int) -> str:
    """The `[V4+ Styles]` line: everything that does not change per word."""
    # `font_size_pct` is an em, the same thing the preview passes to CSS
    # `font-size`. ASS Fontsize is the font's ascent-to-descent height instead,
    # so it has to be scaled by the face's own ratio or the burn comes out
    # smaller than the preview promised — and wraps in different places.
    em = height * style["font_size_pct"] / 100
    font_size = max(1, int(round(em * face_for_style(style).height_ratio)))
    # Halved: libass draws the outline entirely outside the glyph, while the
    # preview's `-webkit-text-stroke` is centred on it and only shows half.
    outline = round(height * style["outline_pct"] / 100 / 2, 1)
    shadow = round(height * style["shadow_pct"] / 100, 1)

    side_margin = int(round(width * (100 - style["max_width_pct"]) / 200))
    # Alignment 2 anchors to the bottom, so the vertical position is expressed
    # as the distance from it.
    bottom_margin = max(0, int(round(height * (100 - style["position_pct"]) / 100)))

    box_color = style.get("box_color")
    if box_color:
        # BorderStyle 3 fills a box behind the text using the outline colour,
        # which is what "background block" means in ASS terms.
        border_style = 3
        outline_color = ass_color(box_color)
        # Padding is expressed against the em, like the preview's, rather than
        # against the (larger) ASS Fontsize.
        outline = max(outline, round(em * 0.15, 1))
    else:
        border_style = 1
        outline_color = ass_color(style["outline_color"], force_opaque=True)

    return (
        f"Style: {STYLE_NAME},{style['font_family']},{font_size},"
        f"{ass_color(style['text_color'], force_opaque=True)},"
        f"{ass_color(style['active_color'], force_opaque=True)},"
        f"{outline_color},"
        f"{ass_color(style['shadow_color'])},"
        f"{-1 if style['bold'] else 0},{-1 if style['italic'] else 0},0,0,"
        f"100,100,0,0,{border_style},{outline},{shadow},2,"
        f"{side_margin},{side_margin},{bottom_margin},1"
    )


def build_overlay_style_line(overlay: OverlayText, width: int, height: int,
                             name: str = OVERLAY_STYLE_NAME) -> str:
    """The `[V4+ Styles]` line for the overlay title.

    The same em-to-Fontsize conversion and halved outline as a caption style —
    the overlay is previewed in CSS by the same rules — but anchored to the top
    of the frame (alignment 8), because a title hangs off the top edge rather
    than sitting above the bottom one.

    `name` is a parameter because a thumbnail draws two of these at once — the
    clip's title and a line written for the still alone — and two blocks of
    text with different sizes and positions cannot share one style.
    """
    em = height * overlay.font_size_pct / 100
    face = resolve_face(overlay.font_family, overlay.bold, overlay.italic)
    font_size = max(1, int(round(em * face.height_ratio)))
    outline = round(height * overlay.outline_pct / 100 / 2, 1)

    side_margin = int(round(width * (100 - overlay.max_width_pct) / 200))
    top_margin = max(0, int(round(height * overlay.position_pct / 100)))

    if overlay.box_color:
        border_style = 3
        outline_color = ass_color(overlay.box_color)
        outline = max(outline, round(em * 0.15, 1))
    else:
        border_style = 1
        outline_color = ass_color(overlay.outline_color, force_opaque=True)

    return (
        f"Style: {name},{overlay.font_family},{font_size},"
        f"{ass_color(overlay.text_color, force_opaque=True)},"
        f"{ass_color(overlay.text_color, force_opaque=True)},"
        f"{outline_color},"
        f"{ass_color('#000000')},"
        f"{-1 if overlay.bold else 0},{-1 if overlay.italic else 0},0,0,"
        f"100,100,0,0,{border_style},{outline},0,8,"
        f"{side_margin},{side_margin},{top_margin},1"
    )


def overlay_body(overlay: OverlayText) -> str:
    """The title's text as libass will read it, line breaks and case included."""
    # A typed line break is kept as one: `\N` is libass's hard break, and the
    # preview draws the same text in a block that honours newlines.
    body = "\\N".join(escape_text(line) for line in overlay.text.strip().splitlines())
    return body.upper() if overlay.uppercase else body


def build_overlay_event(overlay: OverlayText) -> Optional[str]:
    """The one Dialogue line the title draws, faded in and out.

    Layer 1, so a title that overlaps a caption sits over it rather than under.
    """
    if not overlay.is_visible():
        return None

    # `\fad` takes milliseconds, and libass clamps a fade longer than the event
    # itself, so an overlay that is all fade still shows.
    fade = f"{{\\fad({int(overlay.fade_in * 1000)},{int(overlay.fade_out * 1000)})}}"
    return (
        f"Dialogue: 1,{ass_timestamp(overlay.start)},{ass_timestamp(overlay.end)},"
        f"{OVERLAY_STYLE_NAME},,0,0,0,,{fade}{overlay_body(overlay)}"
    )


def build_header(style: Dict[str, Any], width: int, height: int,
                 overlay: Optional[OverlayText] = None) -> str:
    """Script and style sections. `PlayResX/Y` is what the percentages resolve against."""
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        # 1 = fill each line before breaking, which is what the browser does.
        # The default (0) balances lines instead, so a cue that is one line in
        # the preview can come back as two of equal length in the burn.
        "WrapStyle: 1",
        "ScaledBorderAndShadow: yes",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        build_style_line(style, width, height),
    ]
    # Declared only when something uses it: a style block naming a font the box
    # does not have makes libass resolve a face for nothing.
    if overlay is not None and overlay.is_visible():
        lines.append(build_overlay_style_line(overlay, width, height))
    lines.extend([
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ])
    return "\n".join(lines)


def _dialogue(start: float, end: float, text: str) -> str:
    return f"Dialogue: 0,{ass_timestamp(start)},{ass_timestamp(end)},{STYLE_NAME},,0,0,0,,{text}"


def _animated_cue_events(cue: CaptionCue, style: Dict[str, Any]) -> List[str]:
    """One event per word, the spoken one recoloured and optionally popped."""
    active_color = ass_color(style["active_color"], force_opaque=True)
    scale = int(round(style["active_scale"] * 100))
    events = []

    for position, word in enumerate(cue.words):
        # The word owns the screen until the next one starts, so the caption
        # never blanks between words inside a cue.
        segment_start = word.start if position else cue.start
        segment_end = cue.words[position + 1].start if position + 1 < len(cue.words) else cue.end
        if segment_end <= segment_start:
            continue

        rendered = []
        for index, other in enumerate(cue.words):
            body = _word_text(other.text, style)
            if index != position:
                rendered.append(body)
                continue
            override = f"\\c{active_color}&"
            if scale != 100:
                # Scales up over 120ms from the resting size, so the word lands
                # on the beat instead of snapping.
                override += f"\\fscx100\\fscy100\\t(0,120,\\fscx{scale}\\fscy{scale})"
            rendered.append(f"{{{override}}}{body}{{\\r}}")
        events.append(_dialogue(segment_start, segment_end, " ".join(rendered)))

    return events


def build_events(cues: Sequence[CaptionCue], style: Dict[str, Any]) -> List[str]:
    animated = style["animation"] in ("karaoke", "word")
    events: List[str] = []
    for cue in cues:
        if cue.end <= cue.start or not cue.words:
            continue
        if animated:
            events.extend(_animated_cue_events(cue, style))
        else:
            text = " ".join(_word_text(word.text, style) for word in cue.words)
            events.append(_dialogue(cue.start, cue.end, text))
    return events


def render_ass(cues: Sequence[CaptionCue], style: Dict[str, Any], width: int, height: int,
               overlay: Optional[OverlayText] = None) -> str:
    """The complete ASS file for one clip: its captions and its title, if any.

    Both live in one file because ffmpeg burns one subtitle filter per clip, and
    because a title that has to sit over a caption can only be ordered against
    it inside the same script.
    """
    lines = [build_header(style, width, height, overlay)]
    lines.extend(build_events(cues, style))
    if overlay is not None:
        event = build_overlay_event(overlay)
        if event:
            lines.append(event)
    return "\n".join(lines) + "\n"


# A still is one frame, so everything drawn on it is drawn from the first
# moment of the script and stays. Ten seconds is simply longer than the one
# frame ffmpeg will take out of it.
STILL_DURATION = 10.0


def _still_cue_event(cue: CaptionCue, style: Dict[str, Any], time: float) -> Optional[str]:
    """The caption a viewer would see at `time`, frozen with no animation.

    The word being spoken keeps the active colour it has in the video, because
    that is what the frame at that instant actually looks like — but not the
    scale-up, which is a 120ms movement and a still has no movement to show.
    """
    if not cue.words:
        return None
    active_color = ass_color(style["active_color"], force_opaque=True)
    # The active word holds until the next one starts, the same rule the burned
    # events and the browser overlay follow.
    active = max(
        (index for index, word in enumerate(cue.words) if time >= word.start),
        default=0,
    )
    animated = style["animation"] in ("karaoke", "word")

    rendered = []
    for index, word in enumerate(cue.words):
        body = _word_text(word.text, style)
        if animated and index == active:
            body = f"{{\\c{active_color}&}}{body}{{\\r}}"
        rendered.append(body)
    return _dialogue(0.0, STILL_DURATION, " ".join(rendered))


def render_still_ass(cues: Sequence[CaptionCue], style: Dict[str, Any], width: int, height: int,
                     overlays: Sequence[OverlayText], time: float) -> str:
    """An ASS script describing one frozen frame, for burning onto a thumbnail.

    Not a shortened `render_ass`: a thumbnail is extracted by seeking the source
    and taking a single frame, which arrives at timestamp zero however far into
    the clip it came from. So everything that should appear on it — the caption
    that covers `time`, the clip's title, any text written for the still alone —
    is emitted at zero, with the fades dropped. What the frame keeps is the
    *look*: the same styles, the same font sizes as fractions of the same
    frame, so the thumbnail and the video agree about where the words sit.

    `overlays` are drawn in order, each on its own layer above the captions.
    """
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "WrapStyle: 1",
        "ScaledBorderAndShadow: yes",
        f"PlayResX: {width}",
        f"PlayResY: {height}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        build_style_line(style, width, height),
    ]
    names = [f"{OVERLAY_STYLE_NAME}{position}" for position in range(len(overlays))]
    for overlay, name in zip(overlays, names):
        lines.append(build_overlay_style_line(overlay, width, height, name))
    lines.extend([
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ])

    cue = next((candidate for candidate in cues if candidate.start <= time < candidate.end), None)
    if cue is not None:
        event = _still_cue_event(cue, style, time)
        if event:
            lines.append(event)

    for layer, (overlay, name) in enumerate(zip(overlays, names), start=1):
        lines.append(
            f"Dialogue: {layer},{ass_timestamp(0.0)},{ass_timestamp(STILL_DURATION)},"
            f"{name},,0,0,0,,{overlay_body(overlay)}"
        )

    return "\n".join(lines) + "\n"
