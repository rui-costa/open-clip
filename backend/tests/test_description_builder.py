"""Cover for the YouTube description template: what it fills in and what it drops."""

import json
from datetime import datetime
from pathlib import Path

from backend.src.dataclasses.data import DescriptionSettings, Highlight, Project, ProjectSettings
from backend.src.services.description_builder import (
    DEFAULT_TEMPLATE,
    build_description,
    build_fields,
    render_template,
    resolve_template,
)


class FakeProject:
    """Just the two things the builder reads off a project."""

    def __init__(self, name="Episode 12", **description):
        self.name = name
        self.settings = ProjectSettings(
            aspect_ratio="9:16",
            resolution="1080p",
            description=DescriptionSettings(**description),
        )


def highlight(**overrides):
    fields = dict(
        highlight_text="the quote",
        viral_hook_text="the hook",
        video_description_for_x="x post",
        video_description_for_reddit="reddit post",
        video_description_for_linkedin="linkedin post",
        video_title_for_youtube_short="the title",
        video_description_for_youtube_short="what the short is about",
        start=0.0,
        end=30.0,
    )
    fields.update(overrides)
    return Highlight(**fields)


def test_placeholder_is_replaced_and_plain_text_is_kept():
    project = FakeProject()
    template = "this is a text\n{highlights.ai_video_description}"

    rendered = render_template(template, build_fields(project, highlight(), {}))

    assert rendered == "this is a text\nwhat the short is about"


def test_source_video_is_referenced_by_title_and_url():
    project = FakeProject(
        source_title="The Podcast",
        source_url="https://youtu.be/abc123",
    )

    rendered = build_description(project, highlight(), {})

    assert "This is a short from the original podcast The Podcast." in rendered
    # The link is what YouTube uses to connect the short back to the episode.
    assert "https://youtu.be/abc123" in rendered


def test_lines_whose_fields_are_all_empty_are_dropped():
    project = FakeProject()  # no source video filled in

    rendered = build_description(project, highlight(), {})

    assert "original podcast" not in rendered
    assert "Watch the full episode" not in rendered
    assert rendered == "what the short is about"


def test_global_and_project_text_both_reach_the_description():
    project = FakeProject(source_title="The Podcast", text="Project standing text")

    rendered = build_description(project, highlight(), {"text": "Global standing text"})

    assert "Global standing text" in rendered
    assert "Project standing text" in rendered


def test_project_template_overrides_the_global_one():
    project = FakeProject(template="only this: {highlights.video_title_for_youtube_short}")

    assert resolve_template(project, {"template": "global one"}) == project.settings.description.template
    assert build_description(project, highlight(), {"template": "global one"}) == "only this: the title"


def test_global_template_is_used_when_the_project_has_none():
    project = FakeProject()

    assert resolve_template(project, {"template": "global: {project.name}"}) == "global: {project.name}"
    assert resolve_template(project, {}) == DEFAULT_TEMPLATE


def test_unknown_field_is_left_verbatim_rather_than_silently_dropped():
    project = FakeProject()

    rendered = render_template("keep {project.sorce_url} me", build_fields(project, highlight(), {}))

    assert rendered == "keep {project.sorce_url} me"


def test_braces_can_be_escaped_and_json_survives_a_template():
    project = FakeProject()

    rendered = render_template('{{"key": "value"}}', build_fields(project, highlight(), {}))

    assert rendered == '{"key": "value"}'


def test_blank_runs_left_by_dropped_lines_collapse():
    project = FakeProject(text="closing text")
    template = "{highlights.ai_video_description}\n\n{project.source_url}\n\n{project.text}"

    rendered = render_template(template, build_fields(project, highlight(), {}))

    assert rendered == "what the short is about\n\nclosing text"


def test_a_stored_project_renders_its_own_description(tmp_path, monkeypatch):
    """The same path the API takes: settings off disk, not off a stub."""
    project_dir = tmp_path / "projects" / "proj-1"
    project_dir.mkdir(parents=True)
    (project_dir / "metadata.json").write_text(json.dumps({
        "project_id": "proj-1",
        "name": "Test Project",
        "created_at": datetime.now().isoformat(),
        "files": {},
        "highlights": [{
            "highlight_text": "the quote",
            "video_description_for_youtube_short": "what the short is about",
            "start": 0,
            "end": 30,
        }],
        "video_metadata": {"components": [], "top_recommendations": []},
        "settings": {
            "aspect_ratio": "9:16",
            "resolution": "1080p",
            "description": {"source_title": "The Podcast", "source_url": "https://youtu.be/abc123"},
        },
        "status": None,
        "step_statuses": {},
    }))
    monkeypatch.chdir(tmp_path)

    project = Project("proj-1")
    rendered = build_description(project, project.highlights[0], {})

    assert rendered.splitlines()[0] == "what the short is about"
    assert "The Podcast" in rendered and "https://youtu.be/abc123" in rendered


def test_settings_written_by_an_older_version_load_with_empty_description(tmp_path, monkeypatch):
    project_dir = tmp_path / "projects" / "proj-2"
    project_dir.mkdir(parents=True)
    (project_dir / "metadata.json").write_text(json.dumps({
        "project_id": "proj-2",
        "name": "Old Project",
        "created_at": datetime.now().isoformat(),
        "files": {},
        "highlights": [],
        "video_metadata": {"components": [], "top_recommendations": []},
        "settings": {"aspect_ratio": "16:9", "resolution": "1080p"},
        "status": None,
        "step_statuses": {},
    }))
    monkeypatch.chdir(tmp_path)

    project = Project("proj-2")

    assert project.settings.description == DescriptionSettings()
    # And it survives a save, so the field exists to be edited afterwards.
    project.save()
    stored = json.loads((Path("projects") / "proj-2" / "metadata.json").read_text())
    assert stored["settings"]["description"] == {
        "source_url": "", "source_title": "", "text": "", "template": ""
    }


def test_highlight_and_highlights_prefixes_name_the_same_field():
    fields = build_fields(FakeProject(), highlight(), {})

    assert fields["highlight.ai_video_description"] == "what the short is about"
    assert fields["highlights.ai_video_description"] == "what the short is about"
    assert fields["highlights.video_description_for_youtube_short"] == "what the short is about"
