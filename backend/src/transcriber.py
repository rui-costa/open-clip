import logging
import os

import whisper
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class Transcriber:
    """
    A class for transcribing audio files using OpenAI's Whisper model.
    """
    def __init__(self, model: str = "base"):
        try:
            self.model = whisper.load_model(model)
            logger.info(f"Transcriber initialized with model: {model}")
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise

    def transcribe(
        self,
        audio_file_path: str,
        project_path: Optional[str] = None,
        language: Optional[str] = None,
        progress_callback: Any = None
    ) -> Dict[str, Any]:
        """
        Transcribes an audio file and returns the full result.
        
        Returns:
            Dictionary with full text and word-level timestamps.
        """
        # If project_path is provided, resolve the audio file path relative to it
        actual_path = audio_file_path
        if project_path and not os.path.exists(actual_path):
            potential_path = os.path.join(project_path, audio_file_path)
            if os.path.exists(potential_path):
                actual_path = potential_path
        
        if not os.path.exists(actual_path):
            raise FileNotFoundError(f"Audio file not found: {actual_path}")
        
        if progress_callback:
            progress_callback(0.1)
        
        logger.info(f"Transcribing {actual_path}")
        result = self.model.transcribe(
            actual_path,
            language=language,
            word_timestamps=True,  # Re-enabled, as CLI works with this
            no_speech_threshold=0.6,
            logprob_threshold=-1.0,
            condition_on_previous_text=False,
            verbose=False
        )
        
        if progress_callback:
            progress_callback(0.5)
        
        # PART 1: The "Clean Text" for the LLM
        # One single massive string of the whole transcript
        full_text = result.get("text", "").strip()

        # PART 2: For the Video Editor (Ultra-Compressed Word Map) ---
        # We use short keys: 'w' (word), 's' (start), 'e' (end)
        # We round to 2 decimals to save space without losing sync
        word_map_rows = []
        for segment in result.get("segments", []):
            if "words" in segment:
                for w in segment["words"]:
                    # Clean the word of any internal commas to avoid CSV errors
                    word = w.get("word", "").strip().replace(",", "")
                    start = round(w.get("start", 0), 2)
                    end = round(w.get("end", 0), 2)
                    word_map_rows.append([word, start, end])
        
        return full_text, word_map_rows
