"""Caption style presets, shared by the browser preview and the burned render.

A style is deliberately renderer-neutral: sizes are percentages of the frame,
never pixels, so the same numbers describe a 1080x1920 ASS render and a preview
box of whatever width the browser gave it. That is what makes the preview
honest — both sides read this one object.

Presets live in `backend/config/caption_styles.json` alongside the other
config-driven maps (aspect ratios, resolutions). A project stores a preset name
plus any per-project overrides; `resolve_style` flattens the two into the object
both renderers consume.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "caption_styles.json"

DEFAULT_PRESET = "karaoke_pop"

ANIMATIONS = ("karaoke", "word", "static")

# The full style contract. Every key is defaulted here, so a preset file that
# omits one — or an older project that stored a partial override — still
# resolves to something both renderers can draw.
STYLE_DEFAULTS: Dict[str, Any] = {
    "label": "Custom",
    "description": "",
    "animation": "karaoke",
    "words_per_cue": 4,
    "font_family": "Arial Black",
    "font_size_pct": 7.0,
    "bold": True,
    "italic": False,
    "uppercase": True,
    "text_color": "#FFFFFF",
    "active_color": "#FFE500",
    "outline_color": "#000000",
    "shadow_color": "#000000",
    "box_color": None,
    "outline_pct": 0.7,
    "shadow_pct": 0.5,
    "position_pct": 78.0,
    "max_width_pct": 86.0,
    "active_scale": 1.14,
}

# Bounds are enforced rather than trusted: these numbers end up in an ASS file
# and in inline CSS, and a caption at 400% of frame height is not a caption.
_NUMERIC_BOUNDS: Dict[str, tuple] = {
    "words_per_cue": (1, 12),
    "font_size_pct": (1.0, 25.0),
    "outline_pct": (0.0, 3.0),
    "shadow_pct": (0.0, 3.0),
    "position_pct": (0.0, 100.0),
    "max_width_pct": (10.0, 100.0),
    "active_scale": (1.0, 2.0),
}

_INT_KEYS = {"words_per_cue"}
_BOOL_KEYS = {"bold", "italic", "uppercase"}
_COLOR_KEYS = {"text_color", "active_color", "outline_color", "shadow_color", "box_color"}


@lru_cache(maxsize=1)
def _load_presets() -> Dict[str, Dict[str, Any]]:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"Could not read caption styles from {CONFIG_PATH}: {e}")
        return {DEFAULT_PRESET: dict(STYLE_DEFAULTS)}

    presets = {}
    for name, values in raw.items():
        if isinstance(values, dict):
            presets[name] = {**STYLE_DEFAULTS, **values}
    if not presets:
        presets[DEFAULT_PRESET] = dict(STYLE_DEFAULTS)
    return presets


def get_presets() -> Dict[str, Dict[str, Any]]:
    """Every preset, fully defaulted. The UI renders this as the style picker."""
    return {name: dict(values) for name, values in _load_presets().items()}


def _clean_color(value: Any, fallback: Any) -> Any:
    """Accepts `#RGB`, `#RRGGBB` or `#RRGGBBAA`; anything else keeps the fallback.

    `None` is meaningful for `box_color` (no background block), so it passes.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        return fallback
    text = value.strip()
    if not text.startswith("#"):
        return fallback
    digits = text[1:]
    if len(digits) not in (3, 6, 8) or any(c not in "0123456789abcdefABCDEF" for c in digits):
        return fallback
    if len(digits) == 3:
        digits = "".join(c * 2 for c in digits)
    return f"#{digits.upper()}"


def _clean_number(key: str, value: Any, fallback: Any) -> Any:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    if number != number or number in (float("inf"), float("-inf")):
        return fallback
    low, high = _NUMERIC_BOUNDS[key]
    number = max(low, min(high, number))
    return int(round(number)) if key in _INT_KEYS else number


def sanitize_style(values: Dict[str, Any]) -> Dict[str, Any]:
    """Coerces a partial, possibly hostile style dict onto the contract."""
    style = dict(STYLE_DEFAULTS)
    for key, value in (values or {}).items():
        if key not in STYLE_DEFAULTS:
            continue
        if key in _COLOR_KEYS:
            style[key] = _clean_color(value, STYLE_DEFAULTS[key])
        elif key in _NUMERIC_BOUNDS:
            style[key] = _clean_number(key, value, STYLE_DEFAULTS[key])
        elif key in _BOOL_KEYS:
            style[key] = bool(value)
        elif key == "animation":
            style[key] = value if value in ANIMATIONS else STYLE_DEFAULTS[key]
        else:
            style[key] = str(value)

    # One word per cue is what "word" means; a preset override that disagrees
    # would put the highlight on a word the viewer cannot see.
    if style["animation"] == "word":
        style["words_per_cue"] = 1
    return style


def resolve_style(preset: Optional[str] = None, overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Flattens `preset` plus per-project `overrides` into one style object."""
    presets = _load_presets()
    name = preset if preset in presets else DEFAULT_PRESET
    base = presets.get(name, STYLE_DEFAULTS)
    if preset and preset not in presets:
        logger.warning(f"Unknown caption preset '{preset}', falling back to '{name}'")
    return sanitize_style({**base, **(overrides or {})})
