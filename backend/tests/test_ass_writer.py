from backend.src.services.ass_writer import (
    ass_color,
    ass_timestamp,
    build_events,
    build_style_line,
    escape_text,
    render_ass,
)
from backend.src.infrastructure.font_metrics import face_for_style
from backend.src.services.caption_builder import CaptionCue, CaptionWord
from backend.src.services.caption_styles import resolve_style


def cue(*words):
    entries = [CaptionWord(text, start, end) for text, start, end in words]
    return CaptionCue(start=entries[0].start, end=entries[-1].end, words=entries)


class TestColor:
    def test_reorders_rgb_into_ass_bgr(self):
        assert ass_color("#112233", force_opaque=True) == "&H00332211"

    def test_alpha_is_inverted_into_transparency(self):
        # CSS #..FF is opaque; ASS 00 is opaque.
        assert ass_color("#00000000") == "&HFF000000"
        assert ass_color("#000000FF") == "&H00000000"

    def test_missing_alpha_is_opaque(self):
        assert ass_color("#FFFFFF") == "&H00FFFFFF"


class TestTimestamp:
    def test_formats_centiseconds(self):
        assert ass_timestamp(0) == "0:00:00.00"
        assert ass_timestamp(65.25) == "0:01:05.25"
        assert ass_timestamp(3661.5) == "1:01:01.50"

    def test_negative_time_clamps_to_zero(self):
        assert ass_timestamp(-4) == "0:00:00.00"

    def test_rounding_never_produces_a_hundred_centiseconds(self):
        assert ass_timestamp(1.999) == "0:00:01.99"


class TestEscaping:
    def test_braces_cannot_open_an_override_block(self):
        assert "{" not in escape_text("{\\c&HFF0000&}")

    def test_newlines_do_not_break_the_event_line(self):
        assert "\n" not in escape_text("two\nlines")


class TestStyleLine:
    def test_sizes_are_resolved_against_the_output_frame(self):
        style = resolve_style("karaoke_pop", {"font_size_pct": 10.0})
        line = build_style_line(style, 1080, 1920)
        # 10% of 1920 as an em, converted into the ascent-to-descent height ASS
        # expects. Read from the resolved face rather than hardcoded: the file
        # behind "Arial Black" differs between a workstation and the container.
        expected = round(192 * face_for_style(style).height_ratio)
        assert f",{expected}," in line

    def test_font_size_is_scaled_out_of_em_into_ass_units(self):
        # The preview draws this size as a CSS em, and every font ASS can be
        # asked for is taller than its em, so the number in the file has to come
        # out larger — otherwise the burn is smaller than the preview promised.
        style = resolve_style("karaoke_pop", {"font_size_pct": 10.0})
        font_size = int(build_style_line(style, 1080, 1920).split(",")[2])
        assert font_size > 192

    def test_outline_is_halved_against_the_previews_centred_stroke(self):
        # `-webkit-text-stroke` is centred on the glyph edge, so only half of it
        # shows; libass draws its outline entirely outside.
        style = resolve_style("karaoke_pop", {"outline_pct": 1.0})
        assert build_style_line(style, 1080, 1920).split(",")[16] == "9.6"

    def test_position_becomes_a_bottom_margin(self):
        style = resolve_style("karaoke_pop", {"position_pct": 75.0})
        # 25% of 1920 from the bottom.
        assert build_style_line(style, 1080, 1920).endswith(",480,1")

    def test_a_box_colour_switches_to_the_opaque_box_border_style(self):
        # BorderStyle is the 16th field of a V4+ style line.
        boxed = build_style_line(resolve_style("boxed_bold"), 1080, 1920).split(",")
        plain = build_style_line(resolve_style("karaoke_pop"), 1080, 1920).split(",")
        assert boxed[15] == "3"
        assert plain[15] == "1"


class TestEvents:
    def test_karaoke_emits_one_event_per_word(self):
        style = resolve_style("karaoke_pop")
        events = build_events([cue(("one", 0.0, 0.4), ("two", 0.4, 0.8))], style)
        assert len(events) == 2
        # Every event carries the whole cue; only the highlight moves.
        assert all("one" in event.lower() and "two" in event.lower() for event in events)

    def test_the_spoken_word_is_the_one_recoloured(self):
        style = resolve_style("karaoke_pop", {"active_color": "#FF0000", "uppercase": False})
        first, second = build_events([cue(("one", 0.0, 0.4), ("two", 0.4, 0.8))], style)
        assert "\\c&H000000FF&" in first and "}one{\\r} two" in first
        assert "\\c&H000000FF&" in second and "}two{\\r}" in second
        assert second.split("{")[0].endswith("one ")

    def test_the_first_word_holds_from_the_cue_start(self):
        style = resolve_style("karaoke_pop")
        held = cue(("one", 0.5, 0.9), ("two", 0.9, 1.3))
        held.start = 0.4
        assert build_events([held], style)[0].startswith("Dialogue: 0,0:00:00.40")

    def test_static_style_emits_one_event_for_the_whole_cue(self):
        style = resolve_style("clean_lines")
        events = build_events([cue(("one", 0.0, 0.4), ("two", 0.4, 0.8))], style)
        assert len(events) == 1

    def test_uppercase_is_applied_to_the_rendered_text(self):
        style = resolve_style("karaoke_pop", {"uppercase": True})
        assert "ONE" in build_events([cue(("one", 0.0, 0.4))], style)[0]

    def test_an_empty_cue_is_skipped(self):
        empty = CaptionCue(start=1.0, end=2.0, words=[])
        assert build_events([empty], resolve_style("karaoke_pop")) == []


class TestRender:
    def test_declares_the_frame_the_percentages_resolve_against(self):
        text = render_ass([cue(("hi", 0.0, 0.4))], resolve_style("karaoke_pop"), 1080, 1920)
        assert "PlayResX: 1080" in text
        assert "PlayResY: 1920" in text
        assert "[Events]" in text

    def test_no_cues_still_produces_a_loadable_file(self):
        text = render_ass([], resolve_style("karaoke_pop"), 1080, 1920)
        assert "[V4+ Styles]" in text
        assert "Dialogue:" not in text
