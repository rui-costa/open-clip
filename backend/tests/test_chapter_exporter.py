import pytest

from backend.src.services.chapter_exporter import (
    NoChaptersError,
    build_chapter_edl,
    build_youtube_chapters,
    format_timestamp,
    parse_timestamp,
)


class FakeProject:
    """Stands in for Project: the exporter only reads these three things."""

    def __init__(self, chapters, name="Episode 12"):
        self.project_id = "test-project"
        self.name = name
        self.llm_outputs = {"chapters": {"chapters": chapters}} if chapters is not None else {}

    def get_artifact_path(self, key):
        # No source video on disk, so the exporter falls back to DEFAULT_FPS.
        return "missing.mp4"


def chapter(time, title):
    return {"chapter_time": time, "chapter_title": title}


# --- timestamps ------------------------------------------------------------

@pytest.mark.parametrize(
    "value,expected",
    [
        ("00:00:00", 0),
        ("00:01:45", 105),
        ("1:45", 105),
        ("01:02:03", 3723),
        ("90", 90),
        (12.5, 12.5),
    ],
)
def test_parse_timestamp_accepts_the_forms_models_emit(value, expected):
    assert parse_timestamp(value) == expected


@pytest.mark.parametrize("value", ["", "soon", "1:2:3:4", None, "-5", True])
def test_parse_timestamp_rejects_junk(value):
    assert parse_timestamp(value) is None


def test_format_timestamp_drops_the_hour_until_a_chapter_needs_it():
    assert format_timestamp(105, with_hours=False) == "1:45"
    assert format_timestamp(3723, with_hours=True) == "1:02:03"


# --- youtube ---------------------------------------------------------------

def test_youtube_chapters_render_one_line_each():
    project = FakeProject([chapter("00:00:00", "Intro"), chapter("00:01:45", "Origin story")])

    assert build_youtube_chapters(project) == "0:00 Intro\n1:45 Origin story"


def test_youtube_chapters_switch_to_hours_when_the_video_is_long():
    project = FakeProject([chapter("00:00:00", "Intro"), chapter("01:02:03", "Late topic")])

    # YouTube needs every stamp in the same shape once one of them has an hour.
    assert build_youtube_chapters(project) == "0:00:00 Intro\n1:02:03 Late topic"


def test_chapters_are_sorted_by_time():
    project = FakeProject([chapter("00:05:00", "Later"), chapter("00:00:00", "Intro")])

    assert build_youtube_chapters(project).startswith("0:00 Intro")


def test_unreadable_chapter_is_skipped_not_fatal():
    project = FakeProject([chapter("00:00:00", "Intro"), chapter("whenever", "Broken")])

    assert build_youtube_chapters(project) == "0:00 Intro"


def test_missing_chapters_names_the_query_to_run():
    with pytest.raises(NoChaptersError, match="Chapters query"):
        build_youtube_chapters(FakeProject(None))


def test_all_chapters_unreadable_is_an_error():
    with pytest.raises(NoChaptersError):
        build_youtube_chapters(FakeProject([chapter("nope", "Broken")]))


# --- edl -------------------------------------------------------------------

def test_chapter_edl_markers_run_up_to_the_next_chapter():
    project = FakeProject([chapter("00:00:00", "Intro"), chapter("00:00:10", "Next")])

    edl = build_chapter_edl(project, fps=30.0)

    assert "TITLE: Episode 12 Chapters" in edl
    # 10s at 30fps, so the first marker is 300 frames long and the second gets
    # the trailing default.
    assert "|M:Intro |D:300" in edl
    assert "|M:Next |D:150" in edl
    # Record timecodes are offset by the Resolve timeline start.
    assert "01:00:00:00 01:00:10:00" in edl


def test_chapter_edl_respects_a_custom_timeline_start():
    project = FakeProject([chapter("00:00:00", "Intro")])

    edl = build_chapter_edl(project, fps=30.0, record_start="00:00:00:00")

    assert "00:00:00:00 00:00:05:00" in edl
