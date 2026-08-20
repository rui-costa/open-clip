import pytest

from backend.src.dataclasses.data import WordMapEntry
from backend.src.services.caption_builder import (
    build_cues,
    group_into_cues,
    words_in_window,
    CaptionWord,
)


def entries(*rows):
    return [WordMapEntry(word=word, start=start, end=end) for word, start, end in rows]


class TestWordsInWindow:
    def test_rebases_times_to_the_clip(self):
        words = words_in_window(entries(("hello", 10.0, 10.4), ("there", 10.4, 10.9)), 10.0, 12.0)
        assert [w.text for w in words] == ["hello", "there"]
        assert [w.start for w in words] == pytest.approx([0.0, 0.4])
        assert [w.end for w in words] == pytest.approx([0.4, 0.9])

    def test_drops_words_outside_the_window(self):
        words = words_in_window(entries(("before", 1.0, 2.0), ("inside", 11.0, 11.5)), 10.0, 12.0)
        assert [w.text for w in words] == ["inside"]

    def test_keeps_and_clamps_a_word_straddling_the_cut(self):
        # The word is audible in the clip, so captioning has to cover it.
        words = words_in_window(entries(("straddle", 9.5, 10.5)), 10.0, 12.0)
        assert words[0].start == 0.0
        assert words[0].end == pytest.approx(0.5)

    def test_gives_a_zero_length_entry_something_to_show(self):
        words = words_in_window(entries(("blip", 10.0, 10.0)), 10.0, 12.0)
        assert words[0].end > words[0].start

    def test_sorts_out_of_order_entries(self):
        words = words_in_window(entries(("second", 11.0, 11.2), ("first", 10.0, 10.2)), 10.0, 12.0)
        assert [w.text for w in words] == ["first", "second"]


class TestGrouping:
    def words(self, count, step=0.3):
        return [CaptionWord(f"w{i}", i * step, i * step + step * 0.9) for i in range(count)]

    def test_respects_the_word_budget(self):
        cues = group_into_cues(self.words(9), words_per_cue=4)
        assert [len(cue.words) for cue in cues] == [4, 4, 1]

    def test_breaks_on_a_long_pause(self):
        words = [CaptionWord("a", 0.0, 0.2), CaptionWord("b", 2.0, 2.2)]
        cues = group_into_cues(words, words_per_cue=4, gap_break=0.6)
        assert [cue.text for cue in cues] == ["a", "b"]

    def test_breaks_at_the_end_of_a_sentence(self):
        words = [CaptionWord("done.", 0.0, 0.2), CaptionWord("next", 0.3, 0.5)]
        cues = group_into_cues(words, words_per_cue=4)
        assert [cue.text for cue in cues] == ["done.", "next"]

    def test_holds_a_cue_but_never_past_the_next_one(self):
        words = [CaptionWord("a", 0.0, 0.2), CaptionWord("b", 0.25, 0.45)]
        cues = group_into_cues(words, words_per_cue=1, hold=0.2)
        assert cues[0].end == cues[1].start
        assert cues[1].end == 0.65

    def test_hold_never_shortens_a_cue(self):
        words = [CaptionWord("a", 0.0, 0.9), CaptionWord("b", 0.5, 1.0)]
        cues = group_into_cues(words, words_per_cue=1, hold=0.2)
        assert cues[0].end >= 0.9


class TestBuildCues:
    def test_builds_from_the_word_map(self):
        cues = build_cues(
            entries(("And", 0.0, 0.3), ("we", 0.3, 0.42), ("just", 0.42, 0.68), ("lost", 0.68, 0.94)),
            0.0,
            1.0,
            words_per_cue=2,
        )
        assert [cue.text for cue in cues] == ["And we", "just lost"]

    def test_no_words_means_no_cues(self):
        assert build_cues(entries(("far", 90.0, 91.0)), 0.0, 5.0) == []

    def test_serialises_words_with_their_own_timings(self):
        cue = build_cues(entries(("hi", 5.0, 5.4)), 5.0, 6.0)[0].to_dict()
        assert cue["text"] == "hi"
        assert cue["words"] == [{"text": "hi", "start": 0.0, "end": pytest.approx(0.4)}]
