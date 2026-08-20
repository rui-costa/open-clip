"""Discovery of LLM pipeline tasks from the config folder.

A prompt file dropped into `backend/config/prompts/` is a task. The file stem,
lowercased, is the task name and therefore the pipeline step name, so
`CHAPTERS.md` becomes the `chapters` step and its button in the UI. Its schema
is expected at `backend/config/schemas/<name>.json`.

`backend/config/llm_tasks.json` is optional and only carries overrides, keyed by
task name: `template` and `schema` when the file names do not line up,
`depends_on`/`auto_run` to place the step in the pipeline, `is_json` to opt out
of JSON parsing and schema validation, and `result_adapter` to route the output
into a typed field on the project instead of the generic bucket.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path("backend/config/prompts")
SCHEMAS_DIR = Path("backend/config/schemas")
TASKS_CONFIG_PATH = Path("backend/config/llm_tasks.json")

PROMPT_SUFFIX = ".md"

# A prompt needs the transcript to be worth running, and a new task is not
# added to the automatic run until its config says so.
DEFAULT_DEPENDS_ON = ["transcription"]
DEFAULT_AUTO_RUN = False


class SchemaNotFoundError(FileNotFoundError):
    """Raised when a task has no schema document to validate its output against."""


@dataclass
class LLMTask:
    name: str
    template: Path
    schema: Path
    is_json: bool = True
    depends_on: List[str] = field(default_factory=lambda: list(DEFAULT_DEPENDS_ON))
    auto_run: bool = DEFAULT_AUTO_RUN
    result_adapter: Optional[str] = None

    def load_template(self) -> str:
        return Path(self.template).read_text(encoding="utf-8")

    def load_schema(self) -> Dict[str, Any]:
        """Loads the task schema, raising SchemaNotFoundError when it is absent."""
        path = Path(self.schema)
        if not path.exists():
            raise SchemaNotFoundError(
                f"No schema for task '{self.name}' at {path}. "
                f"Add a JSON Schema document there describing the output of "
                f"{self.template}, or set \"is_json\": false for this task in "
                f"{TASKS_CONFIG_PATH}."
            )
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def to_step_config(self) -> Dict[str, Any]:
        """The pipeline.json-shaped entry this task contributes.

        `llm` marks the step as prompt-backed so the UI can collapse every such
        step behind one button.
        """
        return {
            "command": self.name,
            "depends_on": list(self.depends_on),
            "auto_run": self.auto_run,
            "llm": True,
        }


def _load_overrides(config_path: Path) -> Dict[str, Dict[str, Any]]:
    if not Path(config_path).exists():
        return {}
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Ignoring unreadable LLM task config {config_path}: {e}")
        return {}
    return data if isinstance(data, dict) else {}


def _build_task(
    name: str,
    template: Path,
    overrides: Dict[str, Any],
    schemas_dir: Path,
) -> LLMTask:
    schema = overrides.get("schema")
    return LLMTask(
        name=name,
        template=Path(overrides.get("template", template)),
        schema=Path(schema) if schema else Path(schemas_dir) / f"{name}.json",
        is_json=overrides.get("is_json", True),
        depends_on=list(overrides.get("depends_on", DEFAULT_DEPENDS_ON)),
        auto_run=overrides.get("auto_run", DEFAULT_AUTO_RUN),
        result_adapter=overrides.get("result_adapter"),
    )


def discover_tasks(
    prompts_dir: Path = PROMPTS_DIR,
    schemas_dir: Path = SCHEMAS_DIR,
    config_path: Path = TASKS_CONFIG_PATH,
) -> Dict[str, LLMTask]:
    """Returns every LLM task, keyed by name, in prompt-file order."""
    overrides = _load_overrides(Path(config_path))
    prompts_dir = Path(prompts_dir)

    tasks: Dict[str, LLMTask] = {}
    # A config entry naming its own template consumes that file, so
    # VIDEO_META.md backing the `metadata` step does not also auto-register a
    # separate `video_meta` step.
    claimed = {
        Path(entry["template"]).resolve()
        for entry in overrides.values()
        if isinstance(entry, dict) and entry.get("template")
    }

    for name, entry in overrides.items():
        if not isinstance(entry, dict):
            logger.warning(f"Ignoring malformed entry for LLM task '{name}' in {config_path}")
            continue
        template = Path(entry.get("template") or prompts_dir / f"{name.upper()}{PROMPT_SUFFIX}")
        if not template.exists():
            logger.warning(
                f"LLM task '{name}' configured in {config_path} has no prompt file at {template}; skipping."
            )
            continue
        tasks[name] = _build_task(name, template, entry, schemas_dir)

    if not prompts_dir.exists():
        logger.warning(f"Prompts directory {prompts_dir} not found; no LLM tasks discovered.")
        return tasks

    for template in sorted(prompts_dir.glob(f"*{PROMPT_SUFFIX}")):
        if template.resolve() in claimed:
            continue
        name = template.stem.lower()
        if name in tasks:
            continue
        tasks[name] = _build_task(name, template, overrides.get(name, {}), schemas_dir)

    return tasks


def get_task(name: str, **kwargs) -> Optional[LLMTask]:
    return discover_tasks(**kwargs).get(name)
