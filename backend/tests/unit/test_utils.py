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


