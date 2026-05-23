import pytest
from unittest.mock import MagicMock, patch
from backend.src.transcriber import Transcriber

@patch('whisper.load_model')
def test_transcriber_init(mock_load):
    Transcriber(model="small")
    mock_load.assert_called_with("small")

@patch('whisper.load_model')
@patch('os.path.exists')
def test_transcriber_process(mock_exists, mock_load):
    mock_exists.return_value = True
    model = mock_load.return_value
    model.transcribe.return_value = {
        "text": "hello world",
        "segments": [
            {
                "words": [{"word": "hello", "start": 0.1, "end": 0.5}, {"word": "world", "start": 0.6, "end": 1.0}]
            }
        ]
    }
    
    t = Transcriber()
    text, words = t.transcribe("fake.mp3")
    assert text == "hello world"
    assert len(words) == 2
    assert words[0] == ["hello", 0.1, 0.5]
