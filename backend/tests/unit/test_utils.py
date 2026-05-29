import pytest
from backend.src.utils import find_highlight_timestamps

def test_find_highlight_timestamps_fuzzy():
    all_words = [
        {'w': 'hello', 's': 0.0, 'e': 0.5},
        {'w': 'world', 's': 1.5, 'e': 2.0}
    ]
    # The snippet "hello world" will trigger fuzzy matching if anchor-based fails or is not applicable
    snippet = "hello world"
    result = find_highlight_timestamps(all_words, snippet)
    assert result['start'] == 0.0
    assert result['end'] == 2.0

def test_find_highlight_timestamps_anchors():
    # CHUNK_SIZE = 5, need 10 words for anchors
    all_words = [{'w': str(i), 's': float(i), 'e': float(i+0.1)} for i in range(12)]
    
    # Anchor 1: 0,1,2,3,4
    # Anchor 2: 7,8,9,10,11
    # Snippet: "0 1 2 3 4 5 6 7 8 9 10 11"
    snippet = " ".join([str(i) for i in range(12)])
    result = find_highlight_timestamps(all_words, snippet)
    assert result['start'] == 0.0
    assert result['end'] == 11.1


import pytest
from backend.src.utils import find_highlight_timestamps

# Helper to build word map entries
def make_word(word, start, end):
    return {"w": word, "s": start, "e": end}

def test_empty_snippet_returns_zero():
    all_words = [make_word("hello", 0.0, 0.5), make_word("world", 0.5, 1.0)]
    result = find_highlight_timestamps(all_words, "")
    assert result == {"start": 0.0, "end": 0.0}

def test_snippet_not_in_all_words_returns_zero():
    all_words = [make_word("foo", 0.0, 0.5), make_word("bar", 0.5, 1.0)]
    result = find_highlight_timestamps(all_words, "missing words")
    assert result == {"start": 0.0, "end": 0.0}

def test_anchor_based_match_success():
    # Build a list with a clear start and end anchor of length 5
    words = ["a", "b", "c", "d", "e", "x", "y", "z", "f", "g", "h", "i", "j", "k", "l", "m", "n", "o", "p", "q"]
    all_words = [make_word(w, i * 0.5, (i + 1) * 0.5) for i, w in enumerate(words)]
    snippet = "a b c d e some middle f g h i j k l m n o p q"
    result = find_highlight_timestamps(all_words, snippet)
    # start should be first word start, end should be end of last anchor word (q)
    assert result["start"] == all_words[0]["s"]
    assert result["end"] == all_words[-1]["e"]

def test_fuzzy_match_success():
    # Words with gaps that still allow fuzzy matching
    all_words = [
        make_word("the", 0.0, 0.2),
        make_word("quick", 0.2, 0.4),
        make_word("brown", 0.4, 0.6),
        make_word("fox", 0.6, 0.8),
        make_word("jumps", 0.8, 1.0),
        make_word("over", 1.0, 1.2),
        make_word("the", 1.2, 1.4),
        make_word("lazy", 1.4, 1.6),
        make_word("dog", 1.6, 1.8),
    ]
    snippet = "quick fox lazy dog"
    result = find_highlight_timestamps(all_words, snippet)
    # start at "quick" (index 1) and end at "dog" (index 8)
    assert result["start"] == all_words[1]["s"]
    assert result["end"] == all_words[8]["e"]

def test_partial_anchor_fallback_to_fuzzy():
    # Provide snippet where anchor size is larger than available words, forcing fuzzy path
    all_words = [make_word("alpha", 0, 0.5), make_word("beta", 0.5, 1.0), make_word("gamma", 1.0, 1.5), make_word("delta", 1.5, 2.0)]
    snippet = "alpha gamma"
    result = find_highlight_timestamps(all_words, snippet)
    # Should match via fuzzy logic, start at alpha (0) end at gamma (1.5)
    assert result["start"] == all_words[0]["s"]
    assert result["end"] == all_words[2]["e"]

def test_whitespace_only_snippet_returns_zero():
    # Covers line 14: snippet that strips to empty
    all_words = [make_word("hello", 0.0, 0.5)]
    result = find_highlight_timestamps(all_words, "   ")
    assert result == {"start": 0.0, "end": 0.0}

def test_fuzzy_end_of_list_boundary():
    # Covers line 60: next_idx goes past end of all_words during gap search
    all_words = [make_word("one", 0.0, 0.5), make_word("two", 0.5, 1.0)]
    # Snippet has second word that doesn't exist anywhere in all_words
    result = find_highlight_timestamps(all_words, "one missing")
    assert result == {"start": 0.0, "end": 0.0}

def test_fuzzy_gap_exhausted():
    # Covers line 67: found_next stays False after all gaps exhausted (word too far away)
    all_words = [make_word("start", 0.0, 0.5)]
    for i in range(10):
        all_words.append(make_word(f"filler{i}", (i + 1) * 0.5, (i + 2) * 0.5))
    # "end" is not in the list at all so gap exhausts
    result = find_highlight_timestamps(all_words, "start end")
    assert result == {"start": 0.0, "end": 0.0}

