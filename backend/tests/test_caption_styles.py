from backend.src.services.caption_styles import (
    DEFAULT_PRESET,
    STYLE_DEFAULTS,
    get_presets,
    resolve_style,
    sanitize_style,
)


class TestPresets:
    def test_every_preset_is_fully_defaulted(self):
        for name, style in get_presets().items():
            missing = set(STYLE_DEFAULTS) - set(style)
            assert not missing, f"preset {name} is missing {missing}"

    def test_the_default_preset_exists(self):
        assert DEFAULT_PRESET in get_presets()


class TestSanitize:
    def test_clamps_a_font_size_that_would_swallow_the_frame(self):
        assert sanitize_style({"font_size_pct": 400})["font_size_pct"] == 25.0

    def test_rejects_a_colour_that_is_not_a_hex_value(self):
        style = sanitize_style({"text_color": "javascript:alert(1)"})
        assert style["text_color"] == STYLE_DEFAULTS["text_color"]

    def test_expands_short_hex(self):
        assert sanitize_style({"active_color": "#f0a"})["active_color"] == "#FF00AA"

    def test_keeps_alpha_on_a_box_colour(self):
        assert sanitize_style({"box_color": "#000000cc"})["box_color"] == "#000000CC"

    def test_no_box_is_a_valid_box_colour(self):
        assert sanitize_style({"box_color": None})["box_color"] is None

    def test_ignores_keys_outside_the_contract(self):
        assert "rm_rf" not in sanitize_style({"rm_rf": True})

    def test_unreadable_numbers_fall_back(self):
        assert sanitize_style({"position_pct": "high"})["position_pct"] == STYLE_DEFAULTS["position_pct"]

    def test_word_animation_forces_one_word_per_cue(self):
        style = sanitize_style({"animation": "word", "words_per_cue": 6})
        assert style["words_per_cue"] == 1

    def test_unknown_animation_falls_back(self):
        assert sanitize_style({"animation": "explode"})["animation"] == STYLE_DEFAULTS["animation"]


class TestResolve:
    def test_overrides_win_over_the_preset(self):
        base = resolve_style("karaoke_pop")
        tweaked = resolve_style("karaoke_pop", {"font_size_pct": 9.0})
        assert base["font_size_pct"] != 9.0
        assert tweaked["font_size_pct"] == 9.0
        # Everything not overridden still comes from the preset.
        assert tweaked["active_color"] == base["active_color"]

    def test_unknown_preset_falls_back_to_the_default(self):
        assert resolve_style("does_not_exist") == resolve_style(DEFAULT_PRESET)
