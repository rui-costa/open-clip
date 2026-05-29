import os
from backend.src.services.transcription_mapper import parse_whisper_result, TranscriptionResult

def test_parse_whisper_result_success():
    """Verify standard whisper output is mapped correctly."""
    raw_input = {
        "text": "hello world",
        "segments": [
            {"words": [{"word": "hello,", "start": 0.123, "end": 0.567}]}
        ]
    }
    result = parse_whisper_result(raw_input)
    
    assert isinstance(result, TranscriptionResult)
    assert result.text == "hello world"
    assert result.word_map == [["hello", 0.12, 0.57]]

def test_parse_whisper_result_empty():
    """Verify empty whisper input results in empty TranscriptionResult."""
    raw_input = {}
    result = parse_whisper_result(raw_input)
    
    assert result.text == ""
    assert result.word_map == []

def test_parse_whisper_result_no_words():
    """Verify segments without word data are handled."""
    raw_input = {
        "text": "no words here",
        "segments": [{"text": "no words here"}]
    }
    result = parse_whisper_result(raw_input)
    
    assert result.text == "no words here"
    assert result.word_map == []

def test_save_methods(tmp_path):
    """Verify file saving methods."""
    result = TranscriptionResult(text="test text", word_map=[["test", 0.0, 1.0]])
    txt_path = tmp_path / "test.txt"
    csv_path = tmp_path / "test.csv"
    
    result.save_transcription_text(str(txt_path))
    result.save_word_map(str(csv_path))
    
    assert txt_path.read_text(encoding="utf-8") == "test text"
    assert csv_path.exists()

