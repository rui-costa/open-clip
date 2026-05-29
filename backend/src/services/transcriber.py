import os
import pytest
import logging
from backend.src.project import Project
from backend.src.services.transcription_mapper import TranscriptionResult, parse_whisper_result
from backend.src.infrastructure.whisper_client import WhisperClient

logger = logging.getLogger(__name__)

class Transcriber:
    """
    A service for transcribing audio files.
    Autonomous and self-contained per ADR-001.
    """
    def _get_paths(self, project: Project) -> tuple[str, str]:
        base_path = os.path.dirname(str(project.files.original_file))
        return (
            os.path.join(base_path, "transcription.txt"),
            os.path.join(base_path, "word_map.csv")
        )

    def reset_metadata(self, project: Project) -> None:
        """Clears transcription artifacts."""
        txt_path, csv_path = self._get_paths(project)
        for path in [txt_path, csv_path]:
            if os.path.exists(path):
                os.remove(path)

    def start_service(self, project: Project) -> None:
        """Internal lifecycle initialization."""
        self.reset_metadata(project)

    def execute(self, project: Project) -> TranscriptionResult:  # pragma: no cover
        """
        Autonomous execution: 
        1. Protocol start
        2. Perform transcription
        3. Persist artifacts
        4. Protocol end
        """
        self.start_service(project)
        
        client = WhisperClient()
        file_path = str(project.files.original_file)
        logger.info(f"Transcribing {file_path}")
        
        result = client.transcribe(
            file_path,
            word_timestamps=True,
            no_speech_threshold=0.6,
            logprob_threshold=-1.0,
            condition_on_previous_text=False,
            verbose=False
        )
        
        transcription_data = parse_whisper_result(result)
        
        # Save artifacts internally
        txt_path, csv_path = self._get_paths(project)
        
        # Save transcription text and word map (using mapper logic)
        transcription_data.save_transcription_text(txt_path)
        transcription_data.save_word_map(csv_path)
            
        self.end_service(project)
        return transcription_data

    def end_service(self, project: Project) -> None:
        """Finalizes the service."""
        pass
