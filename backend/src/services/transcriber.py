import logging
from backend.src.dataclasses.data import Project
from backend.src.services.transcription_mapper import TranscriptionResult, parse_whisper_result
from backend.src.infrastructure.whisper_client import WhisperClient

logger = logging.getLogger(__name__)

class Transcriber:
    """
    A service for transcribing audio files.
    Autonomous and self-contained per ADR-001.
    """
    def reset_metadata(self, project: Project) -> None:
        """Clears transcription artifacts from disk and updates project state."""
        import os
        for field in ["transcription_file", "word_map_file"]:
            path = project.get_artifact_path(field)
            if path.exists():
                os.remove(path)
        project.set_step_status("transcription", "pending")

    def start_service(self, project: Project) -> None:
        """Internal lifecycle initialization."""
        self.reset_metadata(project)
        project.set_step_status("transcription", "running")

    async def execute(self, project: Project) -> TranscriptionResult:  # pragma: no cover
        """
        Autonomous execution: 
        1. Protocol start
        2. Perform transcription
        3. Persist artifacts
        4. Protocol end
        """
        logger.info(f"Transcriber executing for project={project.project_id}")
        self.start_service(project)

        client = WhisperClient()
        file_path = str(project.get_artifact_path("original_file"))
        logger.info(f"Transcriber calling Whisper for file={file_path}")

        result = client.transcribe(
            file_path,
            word_timestamps=True,
            no_speech_threshold=0.6,
            logprob_threshold=-1.0,
            condition_on_previous_text=False,
            verbose=False
        )

        transcription_data = parse_whisper_result(result)
        logger.info(f"Transcriber transcription received, segment_count={len(result.get('segments', []))}")

        # Save artifacts internally
        transcription_data.save(project)

        self.end_service(project)
        logger.info(f"Transcriber completed for project={project.project_id}")
        return transcription_data

    def end_service(self, project: Project) -> None:
        """Finalizes the service."""
        project.set_step_status("transcription", "completed")

