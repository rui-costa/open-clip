"""Regression cover for the highlight EDL, which now shares its builder with chapters."""

from backend.src.dataclasses.data import Highlight
from backend.src.services.marker_exporter import build_edl


def highlight(start, end, hook="Hook", is_clip_generated=False):
    return Highlight(
        highlight_text="text",
        viral_hook_text=hook,
        video_description_for_x="",
        video_description_for_reddit="",
        video_description_for_linkedin="",
        video_title_for_youtube_short="",
        start=start,
        end=end,
        is_clip_generated=is_clip_generated,
    )


def test_events_are_numbered_in_ascending_time_order():
    edl = build_edl([highlight(10, 20, "Second"), highlight(0, 5, "First")], fps=30.0)

    assert edl.index("|M:First") < edl.index("|M:Second")
    assert "001  AX" in edl and "002  AX" in edl


def test_generated_clips_get_their_own_marker_colour():
    edl = build_edl([highlight(0, 5, "Done", is_clip_generated=True)], fps=30.0)

    assert "|C:ResolveColorGreen |M:Done |D:150" in edl


def test_empty_range_is_skipped():
    edl = build_edl([highlight(5, 5, "Empty"), highlight(0, 2, "Kept")], fps=30.0)

    assert "|M:Empty" not in edl
    assert "|M:Kept" in edl
