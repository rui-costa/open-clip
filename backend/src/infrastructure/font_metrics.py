"""Resolves the font a caption will actually be drawn with, and its metrics.

Two renderers draw the same captions — libass at burn time, the browser in the
preview — and they disagree twice unless this module is used:

* They can pick *different files* for the same family name. libass asks
  fontconfig; the browser asks the machine it is running on, which is not the
  same machine when the backend is in Docker. Resolving the file here, and
  serving that same file to the page, makes both draw the same glyphs.
* They read a font size differently. A CSS `font-size` is the em; an ASS
  `Fontsize` is the font's ascent-to-descent height, which for Arial Black is
  1.41 em. The same number therefore comes out ~30% smaller in the burn. The
  ratio below is what the ASS writer multiplies by to cancel that out.

Metrics come from the file's own `head`/`hhea` tables rather than a lookup of
known families, so a preset naming any installed font still lands correctly.
"""

import logging
import struct
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# What an unreadable or unresolvable font is assumed to be. Between Arial's 1.12
# and Arial Black's 1.41, so a font that cannot be measured is wrong by a little
# in either direction rather than badly wrong in one.
DEFAULT_HEIGHT_RATIO = 1.2

# fontconfig is what libass matches through, so asking it the same question is
# what makes the answers agree.
_FC_MATCH_TIMEOUT = 5


@dataclass(frozen=True)
class FontFace:
    """The file libass will draw with, and how to size it the same way."""

    family: str
    path: Optional[Path]
    # ASS Fontsize per em: `Fontsize = em_pixels * height_ratio`.
    height_ratio: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "family": self.family,
            "height_ratio": self.height_ratio,
            "file": str(self.path) if self.path else None,
        }


def _table_directory(data: bytes) -> Dict[str, bytes]:
    """The font's tables, keyed by tag. Handles both TrueType and collections."""
    offset = struct.unpack(">I", data[12:16])[0] if data[:4] == b"ttcf" else 0
    count = struct.unpack(">H", data[offset + 4:offset + 6])[0]
    tables: Dict[str, bytes] = {}
    for index in range(count):
        entry = offset + 12 + index * 16
        tag = data[entry:entry + 4].decode("latin-1")
        start, length = struct.unpack(">II", data[entry + 8:entry + 16])
        tables[tag] = data[start:start + length]
    return tables


def height_ratio(path: Path) -> float:
    """(ascender - descender) / unitsPerEm, which is what libass sizes against."""
    try:
        tables = _table_directory(path.read_bytes())
        units_per_em = struct.unpack(">H", tables["head"][18:20])[0]
        ascender, descender = struct.unpack(">hh", tables["hhea"][4:8])
    except (OSError, KeyError, struct.error, IndexError) as e:
        logger.warning(f"Could not read font metrics from {path}: {e}")
        return DEFAULT_HEIGHT_RATIO
    if not units_per_em or ascender <= descender:
        return DEFAULT_HEIGHT_RATIO
    return (ascender - descender) / units_per_em


def _fc_match(pattern: str) -> Optional[tuple]:
    try:
        result = subprocess.run(
            ["fc-match", "-f", "%{file}\t%{family}", pattern],
            capture_output=True, text=True, timeout=_FC_MATCH_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError) as e:
        # No fontconfig on the box. Captions still render; they are just sized
        # from the default ratio and previewed with whatever font the browser
        # finds for the family name.
        logger.warning(f"fc-match unavailable, falling back to font defaults: {e}")
        return None
    if result.returncode != 0 or "\t" not in result.stdout:
        logger.warning(f"fc-match could not resolve {pattern!r}: {result.stderr.strip()}")
        return None
    path, family = result.stdout.split("\t", 1)
    # fontconfig returns every localised name for a family, comma separated.
    return path.strip(), family.split(",")[0].strip()


@lru_cache(maxsize=32)
def resolve_face(family: str, bold: bool = False, italic: bool = False) -> FontFace:
    """The face libass would draw `family` with, plus its size ratio.

    Weight and slant are part of the *match* rather than something either
    renderer synthesises, so both sides use a real bold face when one exists and
    neither has to fake one.
    """
    pattern = family.strip() or "sans-serif"
    if bold:
        pattern += ":bold"
    if italic:
        pattern += ":italic"

    matched = _fc_match(pattern)
    if not matched:
        return FontFace(family=family, path=None, height_ratio=DEFAULT_HEIGHT_RATIO)

    path = Path(matched[0])
    if not path.is_file():
        logger.warning(f"fc-match pointed at a missing file for {pattern!r}: {path}")
        return FontFace(family=family, path=None, height_ratio=DEFAULT_HEIGHT_RATIO)
    return FontFace(family=matched[1] or family, path=path, height_ratio=height_ratio(path))


def face_for_style(style: Dict[str, object]) -> FontFace:
    """The face for a resolved caption style."""
    return resolve_face(
        str(style.get("font_family", "")),
        bool(style.get("bold")),
        bool(style.get("italic")),
    )
