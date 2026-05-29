import os
import json
import logging
from typing import Dict, Any, List
from backend.src.project import Project
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
from backend.src.project import Project
from backend.src.settings_manager import settings_manager
from backend.src.infrastructure.gemini_client import GeminiClient

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
        """Clears content processing artifacts."""
        if self.task_name == "extract_highlights":
            project.highlights = []

    def start_service(self, project: Project) -> None:
        """Initializes service and resets metadata."""
        self.reset_metadata(project)

    def execute(self, project: Project) -> Any: # pragma: no cover
        self.start_service(project)

        with open(self.TASKS_CONFIG_PATH, "r") as f:
            tasks = json.load(f)

        api_key = settings_manager.get("gemini_api_key")
        if not api_key:
            raise ValueError("Gemini API key not found in settings.")
        client = GeminiClient(api_key=api_key)

        # Load transcript context autonomously
        transcription_path = os.path.dirname(str(project.files.original_file)) + "/transcription.txt"
        with open(transcription_path, "r", encoding="utf-8") as f:
            transcript_text = f.read()

        # Execute task using configured task_name
        task = tasks.get(self.task_name)
        if not task:
            raise ValueError(f"Task '{self.task_name}' not configured in {self.TASKS_CONFIG_PATH}")

        with open(task["template"], "r", encoding="utf-8") as f:
            template = f.read()

        prompt = template.format(transcript_text=transcript_text)
        response = client.generate_content(prompt, is_json=task.get("is_json", True))

        # Update project state autonomously
        result = json.loads(response)

        if self.task_name == "extract_highlights":
            project.highlights = result.get("highlights", [])

        self.end_service(project)
        return {"status": "completed"}

    def end_service(self, project: Project) -> None:
        """Finalizes the service."""
        pass

