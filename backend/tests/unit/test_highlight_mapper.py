import json
from backend.src.services.highlight_mapper import parse_highlights

def test_parse_highlights_success():
    """Verify raw JSON string is parsed and aligned."""
    raw_response = json.dumps({
        "highlights": [{"highlight_text": "start end"}]
    })
    all_words = [{'w': 'start', 's': 1.0, 'e': 2.0}, {'w': 'end', 's': 3.0, 'e': 4.0}]
    
    result = parse_highlights(raw_response, all_words)
    
    assert len(result) == 1
    assert result[0]['start'] == 1.0
    assert result[0]['end'] == 4.0

def test_parse_highlights_shorts_key():
    """Verify it also supports 'shorts' key in JSON."""
    raw_response = json.dumps({
        "shorts": [{"highlight_text": "hello"}]
    })
    all_words = [{'w': 'hello', 's': 0.5, 'e': 1.5}]
    
    result = parse_highlights(raw_response, all_words)
    
    assert len(result) == 1
    assert result[0]['highlight_text'] == "hello"

def test_parse_highlights_missing_text():
    """Verify it skips highlights without text."""
    raw_response = json.dumps({
        "highlights": [{"no_text": "here"}]
    })
    result = parse_highlights(raw_response, [])
    assert result == []

def test_parse_highlights_empty_json():
    """Verify it handles empty object."""
    raw_response = json.dumps({})
    result = parse_highlights(raw_response, [])
    assert result == []
