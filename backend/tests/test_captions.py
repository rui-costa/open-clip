"""The preview and the burned render must not disagree.

Both read their cues and their style from CaptionService, so these cover the
service itself, the settings that feed it, and the clipper's use of it.
"""

import json
from datetime import datetime
from pathlib import Path

import pytest

from backend.src.dataclasses.data import CaptionSettings, Highlight, Project, ProjectSettings
from backend.src.services.captions import CaptionService
from backend.src.services.clipper import Clipper

PROJECT_ID = "caption-project"

WORD_MAP = "\n".join([
    "word,start,end",
    "And,10.0,10.3",
    "we,10.3,10.5",
    "just,10.5,10.8",
    "lost,10.8,11.2",
    "them.,11.2,11.6",
    "Completely,12.4,13.0",
    "gone.,13.0,13.4",
])


def write_project(root: Path, captions=None):
    project_dir = root / "projects" / PROJECT_ID
    project_dir.mkdir(parents=True, exist_ok=True)
    settings = {"aspect_ratio": "9:16", "resolution": "1080p"}
    if captions is not None:
        settings["captions"] = captions
    metadata = {
        "project_id": PROJECT_ID,
        "name": "Caption Project",
        "created_at": datetime.now().isoformat(),
        "files": {},
        "highlights": [
            {"highlight_text": "And we just lost them.", "viral_hook_text": "",
             "video_description_for_x": "", "video_description_for_reddit": "",
             "video_description_for_linkedin": "", "video_title_for_youtube_short": "",
             "start": 10.0, "end": 14.0},
        ],
        "video_metadata": {"components": [], "top_recommendations": []},
        "settings": settings,
        "status": None,
        "step_statuses": {},
    }
    (project_dir / "metadata.json").write_text(json.dumps(metadata))
    (project_dir / "word_map.csv").write_text(WORD_MAP)


@pytest.fixture
def project_root(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    return tmp_path


@pytest.fixture
def project(project_root):
    write_project(project_root, {"enabled": True, "preset": "karaoke_pop", "overrides": {}})
    return Project(PROJECT_ID)


class TestCaptionSettingsPersistence:
    def test_round_trips_through_metadata(self, project_root):
        write_project(project_root, {"enabled": True, "preset": "boxed_bold",
                                     "overrides": {"font_size_pct": 9.0}})
        settings = Project(PROJECT_ID).settings.captions

        assert settings.enabled is True
        assert settings.preset == "boxed_bold"
        assert settings.overrides == {"font_size_pct": 9.0}

    def test_a_project_saved_before_captions_existed_still_loads(self, project_root):
        write_project(project_root, captions=None)
        settings = Project(PROJECT_ID).settings

        assert settings.captions.enabled is False
        assert settings.aspect_ratio == "9:16"

    def test_survives_a_write(self, project):
        project.settings.captions = CaptionSettings(enabled=True, preset="word_punch")
        project.set_property("settings", project.settings)

        stored = json.loads(Path("projects", PROJECT_ID, "metadata.json").read_text())
        assert stored["settings"]["captions"]["preset"] == "word_punch"
        assert Project(PROJECT_ID).settings.captions.preset == "word_punch"

    def test_garbage_in_metadata_does_not_break_loading(self, project_root):
        write_project(project_root, captions="karaoke please")
        assert Project(PROJECT_ID).settings.captions == CaptionSettings()

    def test_settings_from_dict_ignores_keys_it_does_not_own(self):
        settings = ProjectSettings.from_dict({"aspect_ratio": "1:1", "resolution": "720p",
                                              "legacy_field": "ignored"})
        assert settings.aspect_ratio == "1:1"
        assert not hasattr(settings, "legacy_field")


class TestCaptionService:
    def test_cues_cover_the_highlight_window_only(self, project):
        cues = CaptionService().cues(project, project.highlights[0])
        spoken = " ".join(cue.text for cue in cues)

        assert spoken == "And we just lost them. Completely gone."
        assert all(cue.start >= 0 for cue in cues)

    def test_cues_break_at_the_end_of_a_sentence(self, project):
        """With room for the whole sentence, the break still lands on the full
        stop rather than running two sentences into one cue."""
        project.settings.captions = CaptionSettings(
            enabled=True, preset="karaoke_pop", overrides={"words_per_cue": 8}
        )
        cues = CaptionService().cues(project, project.highlights[0])
        assert [cue.text for cue in cues] == ["And we just lost them.", "Completely gone."]

    def test_the_word_budget_closes_a_cue_before_the_sentence_ends(self, project):
        cues = CaptionService().cues(project, project.highlights[0])
        assert [cue.text for cue in cues][0] == "And we just lost"

    def test_the_style_drives_how_many_words_share_a_cue(self, project):
        project.settings.captions = CaptionSettings(
            enabled=True, preset="karaoke_pop", overrides={"words_per_cue": 2}
        )
        cues = CaptionService().cues(project, project.highlights[0])
        assert max(len(cue.words) for cue in cues) == 2

    def test_preview_payload_carries_the_same_style_the_render_uses(self, project):
        service = CaptionService()
        payload = service.preview(project, project.highlights[0])

        assert payload["enabled"] is True
        assert payload["style"] == service.style(project)
        assert payload["duration"] == pytest.approx(4.0)
        assert payload["cues"][0]["words"][0]["text"] == "And"

    def test_a_missing_word_map_yields_no_cues_rather_than_failing(self, project):
        Path("projects", PROJECT_ID, "word_map.csv").unlink()
        assert CaptionService().cues(project, project.highlights[0]) == []

    def test_writes_an_ass_file_at_the_output_frame_size(self, project, tmp_path):
        path = tmp_path / "clip_000.ass"
        written = CaptionService().write_ass(project, project.highlights[0], path, 1080, 1920)

        assert written == path
        text = path.read_text()
        assert "PlayResY: 1920" in text
        assert "Dialogue:" in text

    def test_no_cues_means_no_file(self, project, tmp_path):
        silent = Highlight.from_json({"start": 100.0, "end": 104.0})
        assert CaptionService().write_ass(project, silent, tmp_path / "x.ass", 1080, 1920) is None
        assert not (tmp_path / "x.ass").exists()


class TestClipperWiring:
    def test_writes_the_subtitle_file_next_to_the_clip(self, project, tmp_path):
        clipper = Clipper()
        path = clipper._write_captions(
            project, project.highlights[0], str(tmp_path), "clip_000.mp4", 1080, 1920
        )

        assert path == str(tmp_path / "clip_000.ass")
        assert (tmp_path / "clip_000.ass").exists()

    def test_a_caption_failure_costs_the_captions_not_the_clip(self, project, tmp_path, monkeypatch):
        clipper = Clipper()
        monkeypatch.setattr(
            clipper.captions, "write_ass",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")),
        )

        assert clipper._write_captions(
            project, project.highlights[0], str(tmp_path), "clip_000.mp4", 1080, 1920
        ) is None

    def test_captions_are_off_unless_the_project_turns_them_on(self, project_root):
        write_project(project_root, captions=None)
        assert CaptionService().is_enabled(Project(PROJECT_ID)) is False
