"""A clip may keep its own caption settings, or follow the project.

`Highlight.captions` is None for a clip that has no opinion. That is the locked
state, and it is stored as absence rather than as a copy of the project's
values so that later changes to the project keep reaching it.
"""

from backend.src.dataclasses.data import CaptionSettings, Highlight
from backend.src.services.captions import CaptionService


def highlight(**overrides) -> Highlight:
    data = {
        "highlight_text": "a moment",
        "viral_hook_text": "hook",
        "video_description_for_x": "",
        "video_description_for_reddit": "",
        "video_description_for_linkedin": "",
        "video_title_for_youtube_short": "",
        "start": 1.0,
        "end": 4.0,
    }
    data.update(overrides)
    return Highlight.from_json(data)


class FakeSettings:
    def __init__(self, captions):
        self.captions = captions


class FakeProject:
    def __init__(self, captions):
        self.settings = FakeSettings(captions)


class TestStorage:
    def test_a_highlight_without_captions_is_locked_to_the_project(self):
        assert highlight().captions is None

    def test_older_highlights_predate_the_field_and_read_as_locked(self):
        # Nothing written before this feature has the key at all.
        assert highlight(captions=None).captions is None

    def test_clip_settings_survive_a_round_trip(self):
        original = highlight(
            captions={"enabled": True, "preset": "word_punch", "overrides": {"font_size_pct": 9}}
        )
        restored = Highlight.from_json(original.to_dict())

        assert restored.captions is not None
        assert restored.captions.preset == "word_punch"
        assert restored.captions.overrides == {"font_size_pct": 9}
        assert restored.captions.enabled is True

    def test_a_locked_clip_serialises_as_null_not_as_a_copy(self):
        # Storing a copy would freeze the clip at the project's values as they
        # were when it was saved, which is the opposite of inheriting.
        assert highlight().to_dict()["captions"] is None


class TestResolution:
    def setup_method(self):
        self.service = CaptionService()
        self.project = FakeProject(
            CaptionSettings(enabled=True, preset="karaoke_pop", overrides={"font_size_pct": 5})
        )

    def test_a_locked_clip_resolves_to_the_project_style(self):
        style = self.service.style(self.project, highlight())
        assert style["font_size_pct"] == 5

    def test_an_unlocked_clip_overrides_the_project(self):
        unlocked = highlight(
            captions={"enabled": True, "preset": "karaoke_pop", "overrides": {"font_size_pct": 12}}
        )
        assert self.service.style(self.project, unlocked)["font_size_pct"] == 12
        # The project itself is untouched by the clip's opinion.
        assert self.service.style(self.project)["font_size_pct"] == 5

    def test_a_clip_may_turn_captions_off_while_the_project_leaves_them_on(self):
        muted = highlight(captions={"enabled": False, "preset": "karaoke_pop", "overrides": {}})
        assert self.service.is_enabled(self.project, muted) is False
        assert self.service.is_enabled(self.project) is True

    def test_a_clip_may_turn_captions_on_while_the_project_leaves_them_off(self):
        project = FakeProject(CaptionSettings(enabled=False))
        loud = highlight(captions={"enabled": True, "preset": "karaoke_pop", "overrides": {}})
        assert self.service.is_enabled(project, loud) is True
        assert self.service.is_enabled(project) is False

    def test_a_project_with_no_caption_settings_still_resolves(self):
        assert self.service.style(FakeProject(None), highlight())["font_size_pct"] > 0
