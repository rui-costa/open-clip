import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from backend.src.dataclasses.data import Project, Highlights, VideoMetadata
from backend.src.infrastructure.credentials import LocalCredentialProvider
from backend.src.infrastructure.gemini_client import GeminiClient, describe_error
from backend.src.infrastructure.schema_validator import validate
from backend.src.services.llm_tasks import LLMTask, SchemaNotFoundError, discover_tasks

logger = logging.getLogger(__name__)


@dataclass
class ResultAdapter:
    """Routes a validated LLM result into a typed field on the project."""
    apply: Callable[[Project, Any], None]
    reset: Callable[[Project], None]


def _apply_highlights(project: Project, result: Any) -> None:
    items = result
    if isinstance(result, dict):
        # The prompt asks for "shorts"; older prompts and schemas say "highlights".
        items = result.get("shorts", result.get("highlights", result))
    project.set_property("highlights", Highlights(items).highlights)


def _apply_video_metadata(project: Project, result: Any) -> None:
    project.set_property("video_metadata", VideoMetadata.from_llm(result))


RESULT_ADAPTERS: Dict[str, ResultAdapter] = {
    "highlights": ResultAdapter(
        apply=_apply_highlights,
        reset=lambda project: project.set_property("highlights", []),
    ),
    "video_metadata": ResultAdapter(
        apply=_apply_video_metadata,
        reset=lambda project: project.set_property("video_metadata", VideoMetadata([], [])),
    ),
}


def _render_word_map(project: Project) -> str:
    return "\n".join(
        f"{entry.start:.2f}\t{entry.end:.2f}\t{entry.word}" for entry in project.word_map.entries
    )


def _read_transcript(project: Project) -> str:
    path = project.get_artifact_path("transcription_file")
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# Every placeholder a prompt template is allowed to use. Each one is resolved
# lazily, so a prompt that does not ask for the word map never pays for loading
# it.
CONTEXT_PROVIDERS: Dict[str, Callable[[Project], Any]] = {
    "transcript_text": _read_transcript,
    "word_map": _render_word_map,
    "project_name": lambda project: project.name,
    # The video the clips were cut from. Empty until the user fills it in on
    # the project page, which is why every prompt using them must treat them as
    # optional context rather than something to quote.
    "source_title": lambda project: project.settings.description.source_title,
    "source_url": lambda project: project.settings.description.source_url,
    "highlights": lambda project: json.dumps([h.to_dict() for h in project.highlights], indent=2),
    "video_metadata": lambda project: json.dumps(project.video_metadata.to_dict(), indent=2),
}


# `{{`/`}}` stay supported for prompts written against str.format, but only an
# identifier between single braces is treated as a placeholder. A prompt that
# shows the model the JSON it must return is full of `{` and `"key": value`, and
# none of that should be mistaken for a field to fill.
_FIELD_PATTERN = re.compile(r"\{\{|\}\}|\{([A-Za-z_][A-Za-z0-9_]*)\}")


def template_placeholders(template: str) -> List[str]:
    """The `{name}` fields a template asks for, ignoring braces used as text."""
    names = []
    for match in _FIELD_PATTERN.finditer(template):
        name = match.group(1)
        if name and name not in names:
            names.append(name)
    return names


def build_prompt(template: str, project: Project) -> str:
    """Fills a template with the project context it asks for."""
    context = {}
    for name in template_placeholders(template):
        provider = CONTEXT_PROVIDERS.get(name)
        if provider is None:
            raise ValueError(
                f"Prompt uses unknown placeholder '{{{name}}}'. "
                f"Available placeholders: {', '.join(sorted(CONTEXT_PROVIDERS))}."
            )
        context[name] = provider(project)

    def substitute(match: "re.Match") -> str:
        token = match.group(0)
        if token == "{{":
            return "{"
        if token == "}}":
            return "}"
        return str(context[match.group(1)])

    # Substituted in one pass over the template, so braces inside a transcript
    # are never re-read as placeholders.
    return _FIELD_PATTERN.sub(substitute, template)


class LLMQuery:
    """
    Service for executing LLM queries to process project content.
    Autonomous and self-contained per ADR-001.

    The task is entirely config-driven: the prompt, its schema, and where the
    result lands all come from the task definition, so a new prompt file needs
    no change here.
    """

    def __init__(self, task_name: str, task: Optional[LLMTask] = None):
        self.task_name = task_name
        self._task = task

    @property
    def task(self) -> Optional[LLMTask]:
        if self._task is None:
            self._task = discover_tasks().get(self.task_name)
        return self._task

    @property
    def adapter(self) -> Optional[ResultAdapter]:
        task = self.task
        if task is None or not task.result_adapter:
            return None
        adapter = RESULT_ADAPTERS.get(task.result_adapter)
        if adapter is None:
            logger.warning(
                f"Task '{self.task_name}' names unknown result_adapter "
                f"'{task.result_adapter}'; storing output in llm_outputs instead."
            )
        return adapter

    def reset_metadata(self, project: Project) -> None:
        """Clears this task's output and returns its step to pending."""
        adapter = self.adapter
        if adapter is not None:
            adapter.reset(project)
        else:
            project.clear_llm_output(self.task_name)
        project.set_step_status(self.task_name, "pending")

    def start_service(self, project: Project) -> None:
        """Initializes service and resets metadata."""
        self.reset_metadata(project)
        project.set_step_status(self.task_name, "running")

    def end_service(self, project: Project) -> None:
        """Finalizes the service."""
        project.set_step_status(self.task_name, "completed")

    def fail(self, project: Project, message: str) -> Dict[str, str]:
        project.set_step_status(self.task_name, "error")
        return {"status": "error", "message": message}

    async def execute(self, project: Project) -> Any:  # pragma: no cover
        logger.info(f"LLMQuery executing task={self.task_name} for project={project.project_id}")
        self.start_service(project)
        try:
            task = self.task
            if task is None:
                raise ValueError(
                    f"Task '{self.task_name}' has no prompt in backend/config/prompts."
                )

            template = task.load_template()

            # Resolved before any API call so a task with no schema fails
            # immediately instead of after paying for a generation.
            schema = task.load_schema() if task.is_json else None

            prompt = build_prompt(template, project)

            credential_provider = LocalCredentialProvider()
            api_key = credential_provider.load("gemini_api_key")
            if not api_key:
                raise ValueError("Gemini API key not found in secrets.")
            client = GeminiClient(api_key=api_key)

            logger.info(
                f"LLMQuery sending prompt to Gemini for task={self.task_name}. Prompt length={len(prompt)}"
            )
            logger.debug(f"LLMQuery prompt content: {prompt}")

            response = client.generate_content(prompt, is_json=task.is_json)
            logger.info(
                f"LLMQuery received response from Gemini for task={self.task_name}. Response length={len(response)}"
            )
            logger.debug(f"LLMQuery response content: {response}")

            if not task.is_json:
                project.set_llm_output(self.task_name, response)
                self.end_service(project)
                return {"status": "completed"}

            result = json.loads(response)

            errors = validate(result, schema)
            if errors:
                detail = "; ".join(errors[:10])
                logger.error(
                    f"LLMQuery output for task={self.task_name} does not match {task.schema}: {detail}"
                )
                return self.fail(project, f"Response failed schema validation: {detail}")

            adapter = self.adapter
            if adapter is not None:
                adapter.apply(project, result)
            else:
                project.set_llm_output(self.task_name, result)

            self.end_service(project)
            logger.info(f"LLMQuery completed task={self.task_name} for project={project.project_id}")
            return {"status": "completed"}
        except SchemaNotFoundError as e:
            logger.warning(f"Task '{self.task_name}' cannot run: {e}")
            return self.fail(project, str(e))
        except Exception as e:
            logger.error(f"Error executing {self.task_name}: {describe_error(e)}", exc_info=True)
            return self.fail(project, describe_error(e))
