"""What a highlights run is asked for, and where the answer comes from.

The prompt used to state how many segments to find and how long they may run
in its own text. These tests are about the three layers that replaced those
sentences — the project, the application, and what the prompt ships with — and
about the numbers actually reaching the rendered prompt.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from backend.src.dataclasses.data import HighlightSettings, Project
from backend.src.services import highlight_options
from backend.src.services.highlight_options import (
    DEFAULT_MAX_CLIPS,
    DEFAULT_MAX_DURATION,
    DEFAULT_MIN_CLIPS,
    DEFAULT_MIN_DURATION,
    SETTINGS_KEY,
    resolve,
)
from backend.src.services.llm_query import build_prompt
from backend.src.settings_manager import settings_manager

PROJECT_ID = "highlight-options-project"

REPO_CONFIG = Path(__file__).resolve().parents[1] / "config"
HIGHLIGHTS_PROMPT = REPO_CONFIG / "prompts" / "HIGHLIGHTS.md"


@pytest.fixture
def app_settings(monkeypatch):
    """The application's own settings, replaced wholesale for one test.

    The manager is a module singleton holding what it read at import time, so
    the dictionary is what a test has to stand in front of.
    """
    values = {}
    monkeypatch.setattr(settings_manager, "settings", values)
    return values


@pytest.fixture
def project(tmp_path, monkeypatch):
    """A project on disk with a transcript, so a prompt can be rendered against it."""
    monkeypatch.chdir(tmp_path)
    project_dir = tmp_path / "projects" / PROJECT_ID
    project_dir.mkdir(parents=True)
    (project_dir / "metadata.json").write_text(json.dumps({
        "project_id": PROJECT_ID,
        "name": "Test Project",
        "created_at": datetime.now().isoformat(),
        "files": {},
        "highlights": [],
        "video_metadata": {"components": [], "top_recommendations": []},
        "settings": {"aspect_ratio": "16:9", "resolution": "1080p"},
        "status": None,
        "step_statuses": {},
    }))
    (project_dir / "transcription.txt").write_text("hello world", encoding="utf-8")
    (project_dir / "word_map.csv").write_text(
        "word,start,end\nhello,0.0,0.5\nworld,0.5,1.0\n", encoding="utf-8"
    )
    return Project(PROJECT_ID)


# --- the three layers ------------------------------------------------------

def test_nothing_configured_falls_back_to_what_the_prompt_shipped_with(app_settings, project):
    options = resolve(project)

    assert (options.min_clips, options.max_clips) == (DEFAULT_MIN_CLIPS, DEFAULT_MAX_CLIPS)
    assert (options.min_duration, options.max_duration) == (DEFAULT_MIN_DURATION, DEFAULT_MAX_DURATION)
    assert options.guidance == ""


def test_application_answer_is_used_when_the_project_has_none(app_settings, project):
    app_settings[SETTINGS_KEY] = {"min_clips": 3, "max_clips": 5, "max_duration": 45}

    options = resolve(project)

    assert (options.min_clips, options.max_clips) == (3, 5)
    assert options.max_duration == 45
    # Untouched by the application, so still the shipped answer rather than
    # something inferred from the fields beside it.
    assert options.min_duration == DEFAULT_MIN_DURATION


def test_project_answer_beats_the_application(app_settings, project):
    app_settings[SETTINGS_KEY] = {"min_clips": 3, "max_clips": 20}
    project.settings.highlights = HighlightSettings(min_clips=8, max_clips=None)

    options = resolve(project)

    assert options.min_clips == 8
    # Only the field the project answered is its own; the rest keeps following.
    assert options.max_clips == 20


def test_clearing_a_project_field_puts_it_back_under_the_application(app_settings, project):
    app_settings[SETTINGS_KEY] = {"max_clips": 14}
    project.settings.highlights = HighlightSettings.from_dict({"max_clips": None})

    assert resolve(project).max_clips == 14


# --- ranges that cannot be satisfied ---------------------------------------

def test_a_backwards_range_is_read_as_the_range_it_describes(app_settings, project):
    """A minimum above its maximum would reject every segment found.

    Both ends come from the same place here, so the user typed one range
    backwards; swapping is what they meant, and beats paying for a run that can
    return nothing.
    """
    project.settings.highlights = HighlightSettings(
        min_clips=12, max_clips=4, min_duration=90, max_duration=30
    )

    options = resolve(project)

    assert (options.min_clips, options.max_clips) == (4, 12)
    assert (options.min_duration, options.max_duration) == (30, 90)


def test_a_project_end_that_crosses_an_inherited_one_pulls_it_along(app_settings, project):
    """The more specific answer wins the collision rather than being swapped away.

    Asking this project for clips of at least 90 seconds against an application
    maximum of 60 means 90 — not a silent swap back into the very default the
    project overrode.
    """
    app_settings[SETTINGS_KEY] = {"max_duration": 60}
    project.settings.highlights = HighlightSettings(min_duration=90)

    options = resolve(project)

    assert (options.min_duration, options.max_duration) == (90, 90)


@pytest.mark.parametrize("stored", [
    {"min_clips": 0},
    {"min_clips": -3},
    {"max_clips": 5000},
    {"max_duration": 0},
    {"max_duration": 99999},
    {"min_clips": "seven"},
    {"min_clips": True},
    {"min_duration": None},
])
def test_a_number_out_of_range_is_no_answer_at_all(app_settings, project, stored):
    """Anything unusable reads as "no opinion" rather than reaching the prompt.

    These numbers are written into a prompt: "find 5000 segments" is a bill
    rather than a request, and zero is a run that can return nothing.
    """
    project.settings.highlights = HighlightSettings.from_dict(stored)

    options = resolve(project)

    assert (options.min_clips, options.max_clips) == (DEFAULT_MIN_CLIPS, DEFAULT_MAX_CLIPS)
    assert (options.min_duration, options.max_duration) == (DEFAULT_MIN_DURATION, DEFAULT_MAX_DURATION)


# --- guidance --------------------------------------------------------------

def test_project_guidance_replaces_the_application_line_rather_than_joining_it(app_settings, project):
    app_settings[SETTINGS_KEY] = {"guidance": "prefer strong opinions"}
    project.settings.highlights = HighlightSettings(guidance="only the guest, never the host")

    options = resolve(project)

    assert options.guidance == "only the guest, never the host"
    assert "prefer strong opinions" not in options.guidance


def test_a_project_that_wrote_nothing_follows_the_application_line(app_settings, project):
    app_settings[SETTINGS_KEY] = {"guidance": "prefer strong opinions"}
    project.settings.highlights = HighlightSettings(guidance="   ")

    assert resolve(project).guidance == "prefer strong opinions"


# --- the rendered prompt ---------------------------------------------------

def test_the_shipped_prompt_carries_the_configured_numbers(app_settings, project):
    """What the whole feature is for: the run is told the project's own range."""
    project.settings.highlights = HighlightSettings(
        min_clips=3, max_clips=4, min_duration=20, max_duration=45,
        guidance="skip anything about pricing",
    )

    prompt = build_prompt(HIGHLIGHTS_PROMPT.read_text(encoding="utf-8"), project)

    assert "Extract exactly 3 to 4" in prompt
    assert "20–45 seconds" in prompt
    assert "skip anything about pricing" in prompt
    # The numbers that used to be written into the file must be gone from it,
    # or a project asking for four 45-second clips is also told to return 7–12.
    assert "7 to 12" not in prompt
    assert "18 seconds" not in prompt


def test_whole_seconds_are_written_as_whole_numbers(app_settings, project):
    """`20–45 seconds`, not `20.0–45.0`: the prompt is a sentence."""
    project.settings.highlights = HighlightSettings(min_duration=20, max_duration=45)

    prompt = build_prompt(HIGHLIGHTS_PROMPT.read_text(encoding="utf-8"), project)

    assert "20.0" not in prompt
    assert "45.0" not in prompt


def test_a_prompt_with_no_guidance_is_left_blank_rather_than_broken(app_settings, project):
    prompt = build_prompt(HIGHLIGHTS_PROMPT.read_text(encoding="utf-8"), project)

    assert "{highlight_guidance}" not in prompt
    assert "None" not in prompt.split("SOURCE VIDEO")[0]


def test_resolve_without_a_project_answers_for_the_application(app_settings):
    """The pipeline can ask what a run would do before there is a project to ask about."""
    app_settings[SETTINGS_KEY] = {"min_clips": 2, "max_clips": 3}

    options = highlight_options.resolve()

    assert (options.min_clips, options.max_clips) == (2, 3)
