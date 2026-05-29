import whisper
from typing import Any

class WhisperClient:
    """
    Manages the Whisper model instance and execution.
    """
    def __init__(self, model_name: str = "base"):
        self.model = whisper.load_model(model_name)

    def transcribe(self, file_path: str, **kwargs: Any) -> dict:
        return self.model.transcribe(file_path, **kwargs)
