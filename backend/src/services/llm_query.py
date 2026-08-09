import os
import json
import logging
from typing import Dict, Any, List
from backend.src.dataclasses.data import Project
from backend.src.settings_manager import settings_manager
from backend.src.infrastructure.gemini_client import GeminiClient

logger = logging.getLogger(__name__)

class LLMQuery:
    """
    Service for executing LLM queries to process project content.
    Autonomous and self-contained per ADR-001.
    """
    
    TASKS_CONFIG_PATH = "backend/config/llm_tasks.json"

import os
import json
import logging
from typing import Dict, Any, List
from backend.src.dataclasses.data import Project, Highlight, Highlights, VideoMetadata, VideoComponent
from backend.src.infrastructure.credentials import LocalCredentialProvider
from backend.src.infrastructure.gemini_client import GeminiClient, describe_error

logger = logging.getLogger(__name__)

class LLMQuery:
    """
    Service for executing LLM queries to process project content.
    Autonomous and self-contained per ADR-001.
    """

    TASKS_CONFIG_PATH = "backend/config/llm_tasks.json"

    def __init__(self, task_name: str):
        self.task_name = task_name

    def reset_metadata(self, project: Project) -> None:
        """Clears content processing artifacts and updates project state for this task only."""
        if self.task_name == "extract_highlights":
            project.highlights = []
            project.set_step_status("highlights", "pending")
        elif self.task_name == "generate_metadata":
            project.video_metadata = VideoMetadata([], [])
            project.set_step_status("metadata", "pending")

    def start_service(self, project: Project) -> None:
        """Initializes service and resets metadata."""
        self.reset_metadata(project)
        if self.task_name == "extract_highlights":
            project.set_step_status("highlights", "running")
        elif self.task_name == "generate_metadata":
            project.set_step_status("metadata", "running")

    async def execute(self, project: Project) -> Any: # pragma: no cover
        logger.info(f"LLMQuery executing task={self.task_name} for project={project.project_id}")
        self.start_service(project)
        try:
            with open(self.TASKS_CONFIG_PATH, "r") as f:
                tasks = json.load(f)

            credential_provider = LocalCredentialProvider()
            api_key = credential_provider.load("gemini_api_key")
            if not api_key:
                raise ValueError("Gemini API key not found in secrets.")
            client = GeminiClient(api_key=api_key)
            # Load transcript context autonomously
            transcription_path = project.get_artifact_path("transcription_file")
            with open(transcription_path, "r", encoding="utf-8") as f:
                transcript_text = f.read()

            # Execute task using configured task_name
            task = tasks.get(self.task_name)
            if not task:
                raise ValueError(f"Task '{self.task_name}' not configured in {self.TASKS_CONFIG_PATH}")

            with open(task["template"], "r", encoding="utf-8") as f:
                template = f.read()

            prompt = template.format(transcript_text=transcript_text)
            logger.info(f"LLMQuery sending prompt to Gemini for task={self.task_name}. Prompt length={len(prompt)}")
            logger.debug(f"LLMQuery prompt content: {prompt}")
            
            response = client.generate_content(prompt, is_json=task.get("is_json", True))
            logger.info(f"LLMQuery received response from Gemini for task={self.task_name}. Response length={len(response)}")
            logger.debug(f"LLMQuery response content: {response}")

            # Update project state autonomously
            result = json.loads(response)

            if self.task_name == "extract_highlights":
                items = result.get("shorts", result) if isinstance(result, dict) else result
                project.set_property("highlights", Highlights(items, project).highlights)
            elif self.task_name == "generate_metadata":
                project.set_property("video_metadata", VideoMetadata.from_llm(result))

            self.end_service(project)
            logger.info(f"LLMQuery completed task={self.task_name} for project={project.project_id}")
            return {"status": "completed"}
        except Exception as e:
            logger.error(f"Error executing {self.task_name}: {describe_error(e)}", exc_info=True)
            if self.task_name == "extract_highlights":
                project.set_step_status("highlights", "error")
            elif self.task_name == "generate_metadata":
                project.set_step_status("metadata", "error")
            return {"status": "error", "message": describe_error(e)}

    def end_service(self, project: Project) -> None:
        """Finalizes the service."""
        if self.task_name == "extract_highlights":
            project.set_step_status("highlights", "completed")
        elif self.task_name == "generate_metadata":
            project.set_step_status("metadata", "completed")

