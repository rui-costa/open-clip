"""Turn the project word map into caption cues for one clip.

The transcription step already writes `word_map.csv` with a start and end per
word, so captions need no second pass over the audio: a clip's captions are a
window onto data the project already has.

Times on the returned cues are *relative to the clip*, because that is what
both consumers need — the ASS file is muxed onto a cut that starts at zero, and
the browser preview counts from the top of the highlight window.
"""

import logging
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

# A pause longer than this reads as a new thought, so the cue breaks there even
# if it is under the word budget. Without it a cue can hang on screen across
# silence, then flash three words at once when speech resumes.
DEFAULT_GAP_BREAK = 0.6

# A cue whose last word has stopped still stays up this long, so back-to-back
# cues do not strobe. Never past the next cue's start.
DEFAULT_HOLD = 0.2

# What a word with no duration of its own gets, so it is still drawn.
MIN_WORD_SECONDS = 0.05

SENTENCE_ENDINGS = (".", "!", "?", "…")


@dataclass
class CaptionWord:
    text: str
    start: float
    end: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CaptionCue:
    start: float
    end: float
    words: List[CaptionWord] = field(default_factory=list)

    @property
    def text(self) -> str:
        return " ".join(word.text for word in self.words)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "words": [word.to_dict() for word in self.words],
        }


def _ends_sentence(word: str) -> bool:
    return word.rstrip('"\')]}').endswith(SENTENCE_ENDINGS)


def words_in_window(entries: Iterable[Any], start: float, end: float) -> List[CaptionWord]:
    """Words overlapping `[start, end)`, re-based to the clip and clamped to it.

    Overlap rather than containment: a word straddling the cut is still heard in
    the clip, so dropping it would caption speech that is audible.
    """
    duration = max(0.0, end - start)
    words: List[CaptionWord] = []
    for entry in entries:
        word_start = float(getattr(entry, "start", 0.0))
        word_end = float(getattr(entry, "end", 0.0))
        text = str(getattr(entry, "word", "")).strip()
        if not text:
            continue
        # Transcribers do emit zero-length entries. Given a length here, they
        # take part in the window test and show up like any other word; left
        # alone they would be dropped or drawn for no frames at all.
        if word_end <= word_start:
            word_end = word_start + MIN_WORD_SECONDS
        if word_end <= start or word_start >= end:
            continue
        relative_start = max(0.0, min(duration, word_start - start))
        relative_end = max(relative_start, min(duration, word_end - start))
        if relative_end <= relative_start:
            relative_end = min(duration, relative_start + MIN_WORD_SECONDS)
        words.append(CaptionWord(text=text, start=relative_start, end=relative_end))
    words.sort(key=lambda w: w.start)
    return words


def group_into_cues(
    words: List[CaptionWord],
    words_per_cue: int = 4,
    gap_break: float = DEFAULT_GAP_BREAK,
    hold: float = DEFAULT_HOLD,
    duration: Optional[float] = None,
) -> List[CaptionCue]:
    """Chunks words into on-screen groups.

    A cue closes on whichever comes first: the word budget, a pause, or the end
    of a sentence. Sentence breaks matter more than they look — a cue that runs
    the end of one sentence into the start of the next reads as a single wrong
    sentence for the second or so it is up.
    """
    budget = max(1, int(words_per_cue))
    cues: List[CaptionCue] = []
    current: List[CaptionWord] = []

    for index, word in enumerate(words):
        current.append(word)
        is_last = index == len(words) - 1
        gap_follows = not is_last and (words[index + 1].start - word.end) >= gap_break
        if is_last or len(current) >= budget or gap_follows or _ends_sentence(word.text):
            cues.append(CaptionCue(start=current[0].start, end=current[-1].end, words=current))
            current = []

    for position, cue in enumerate(cues):
        limit = cues[position + 1].start if position + 1 < len(cues) else duration
        held = cue.end + hold
        cue.end = min(held, limit) if limit is not None else held
        # A hold can never shorten a cue below its own speech.
        cue.end = max(cue.end, cue.words[-1].end)

    return cues


def build_cues(
    entries: Iterable[Any],
    start: float,
    end: float,
    words_per_cue: int = 4,
    gap_break: float = DEFAULT_GAP_BREAK,
    hold: float = DEFAULT_HOLD,
) -> List[CaptionCue]:
    """Caption cues for the clip cut from `[start, end)` of the source."""
    duration = max(0.0, end - start)
    words = words_in_window(entries, start, end)
    if not words:
        logger.info(f"No word map entries inside {start}-{end}; clip gets no captions")
        return []
    return group_into_cues(
        words, words_per_cue=words_per_cue, gap_break=gap_break, hold=hold, duration=duration
    )


def build_project_cues(project, start: float, end: float, words_per_cue: int = 4) -> List[CaptionCue]:
    """Cues for a window of a project's source, or none if it has no word map."""
    try:
        entries = project.word_map.entries
    except (FileNotFoundError, KeyError, ValueError) as e:
        logger.warning(f"No usable word map for project {project.project_id}: {e}")
        return []
    return build_cues(entries, start, end, words_per_cue=words_per_cue)
