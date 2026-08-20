"""Highlight timings come from the LLM payload, never from re-matching text.

The clip and its EDL marker are cut from the same two numbers, so anything that
re-derived them at load time could make an exported marker disagree with a clip
that had already been rendered.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from backend.src.dataclasses.data import Highlight, Highlights, Project

PROJECT_ID = "timing-project"


def payload(**overrides):
    data = {
        "highlight_text": "one two three",
        "viral_hook_text": "Hook",
        "start": 12.5,
        "end": 47.25,
    }
    data.update(overrides)
    return data


def test_start_and_end_are_taken_from_the_payload():
    highlight = Highlight.from_json(payload())

    assert (highlight.start, highlight.end) == (12.5, 47.25)


def test_repeated_phrases_do_not_move_the_end():
    # The closing words recur later in the video; only the reported time counts.
    highlight = Highlight.from_json(payload(highlight_text="and that is the point", end=30.0))

    assert highlight.end == 30.0


def test_numeric_strings_are_accepted():
    highlight = Highlight.from_json(payload(start="12.5", end="47.25"))

    assert (highlight.start, highlight.end) == (12.5, 47.25)


@pytest.mark.parametrize("bad", [None, "", "later", True, [1]])
def test_unusable_timestamps_collapse_to_zero(bad):
    highlight = Highlight.from_json(payload(start=bad, end=bad))

    assert (highlight.start, highlight.end) == (0.0, 0.0)


def test_negative_times_are_clamped_to_the_start_of_the_video():
    highlight = Highlight.from_json(payload(start=-3.0))

    assert highlight.start == 0.0


def test_highlights_drops_entries_without_a_usable_range():
    highlights = Highlights([
        payload(),
        payload(start=10.0, end=10.0),
        payload(start=20.0, end=5.0),
        payload(start="unknown", end="unknown"),
        "not an object",
    ]).highlights

    assert [(h.start, h.end) for h in highlights] == [(12.5, 47.25)]


def test_stored_times_survive_a_project_round_trip(tmp_path, monkeypatch):
    project_dir = tmp_path / "projects" / PROJECT_ID
    project_dir.mkdir(parents=True)
    (project_dir / "metadata.json").write_text(json.dumps({
        "project_id": PROJECT_ID,
        "name": "Timing Project",
        "created_at": datetime.now().isoformat(),
        "files": {},
        "highlights": [payload(is_clip_generated=True, generated_clip_filename="clip_000.mp4")],
        "video_metadata": {"components": [], "top_recommendations": []},
        "settings": {"aspect_ratio": "16:9", "resolution": "1080p"},
        "status": None,
        "step_statuses": {},
    }))
    monkeypatch.chdir(tmp_path)

    # No word_map.csv exists here: loading must not need one.
    loaded = Project(PROJECT_ID)

    assert [(h.start, h.end) for h in loaded.highlights] == [(12.5, 47.25)]
    assert loaded.highlights[0].generated_clip_filename == "clip_000.mp4"
