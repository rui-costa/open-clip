import struct
from pathlib import Path

import pytest

from backend.src.infrastructure import font_metrics
from backend.src.infrastructure.font_metrics import (
    DEFAULT_HEIGHT_RATIO,
    FontFace,
    face_for_style,
    height_ratio,
    resolve_face,
)


@pytest.fixture(autouse=True)
def clear_cache():
    resolve_face.cache_clear()
    yield
    resolve_face.cache_clear()


class TestHeightRatio:
    def test_reads_the_ratio_from_a_real_font(self, tmp_path):
        # A minimal font: only the two tables the ratio is read from.
        head = bytes(18) + struct.pack(">H", 1000) + bytes(34)
        hhea = bytes(4) + struct.pack(">hh", 900, -300) + bytes(30)
        path = tmp_path / "fake.ttf"
        path.write_bytes(_font_with({"head": head, "hhea": hhea}))
        assert height_ratio(path) == pytest.approx(1.2)

    def test_an_unreadable_file_falls_back_rather_than_raising(self, tmp_path):
        path = tmp_path / "broken.ttf"
        path.write_bytes(b"not a font")
        assert height_ratio(path) == DEFAULT_HEIGHT_RATIO

    def test_nonsense_metrics_fall_back(self, tmp_path):
        # A descender above the ascender would produce a negative size.
        head = bytes(18) + struct.pack(">H", 1000) + bytes(34)
        hhea = bytes(4) + struct.pack(">hh", 100, 900) + bytes(30)
        path = tmp_path / "odd.ttf"
        path.write_bytes(_font_with({"head": head, "hhea": hhea}))
        assert height_ratio(path) == DEFAULT_HEIGHT_RATIO


class TestResolveFace:
    def test_weight_and_slant_are_part_of_the_match(self, monkeypatch):
        asked = []

        def fake_match(pattern):
            asked.append(pattern)
            return ("/fonts/x.ttf", "X")

        monkeypatch.setattr(font_metrics, "_fc_match", fake_match)
        monkeypatch.setattr(Path, "is_file", lambda self: True)
        monkeypatch.setattr(font_metrics, "height_ratio", lambda path: 1.3)

        resolve_face("Arial", bold=True, italic=True)
        assert asked == ["Arial:bold:italic"]

    def test_no_fontconfig_still_yields_a_usable_face(self, monkeypatch):
        monkeypatch.setattr(font_metrics, "_fc_match", lambda pattern: None)
        face = resolve_face("Arial Black", bold=True)
        assert face == FontFace(family="Arial Black", path=None, height_ratio=DEFAULT_HEIGHT_RATIO)

    def test_a_matched_file_that_is_gone_is_not_served(self, monkeypatch):
        monkeypatch.setattr(font_metrics, "_fc_match", lambda pattern: ("/gone.ttf", "Gone"))
        assert resolve_face("Gone").path is None


class TestFaceForStyle:
    def test_reads_family_weight_and_slant_off_the_style(self, monkeypatch):
        seen = {}

        def fake_resolve(family, bold=False, italic=False):
            seen.update(family=family, bold=bold, italic=italic)
            return FontFace(family, None, DEFAULT_HEIGHT_RATIO)

        monkeypatch.setattr(font_metrics, "resolve_face", fake_resolve)
        face_for_style({"font_family": "Impact", "bold": True, "italic": False})
        assert seen == {"family": "Impact", "bold": True, "italic": False}


def _font_with(tables: dict) -> bytes:
    """A TrueType file carrying just the given tables."""
    directory = bytearray(struct.pack(">IHHHH", 0x00010000, len(tables), 0, 0, 0))
    offset = 12 + 16 * len(tables)
    body = bytearray()
    for tag, data in tables.items():
        directory += tag.encode("latin-1") + struct.pack(">III", 0, offset + len(body), len(data))
        body += data
    return bytes(directory + body)
