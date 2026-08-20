import asyncio
import json
from datetime import datetime
from pathlib import Path

import pytest

from backend.src.dataclasses.data import Project, VideoComponent, VideoMetadata
from backend.src.infrastructure.schema_validator import validate
from backend.src.orchestrator import PipelineOrchestrator
from backend.src.services.llm_query import LLMQuery, build_prompt
from backend.src.services.llm_tasks import SchemaNotFoundError, discover_tasks

PROJECT_ID = "test-project"

CHAPTERS_PROMPT = """Split the transcript.

## TRANSCRIPT:
{transcript_text}

## WORD MAP:
{word_map}

{{
  "chapters": []
}}
"""

CHAPTERS_SCHEMA = {
    "type": "object",
    "properties": {
        "chapters": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chapter_time": {"type": "string"},
                    "chapter_title": {"type": "string"},
                },
                "required": ["chapter_time", "chapter_title"],
            },
        }
    },
    "required": ["chapters"],
}


@pytest.fixture
def config_root(tmp_path, monkeypatch):
    """A config tree with one auto-discovered prompt and one overridden prompt."""
    prompts = tmp_path / "backend" / "config" / "prompts"
    schemas = tmp_path / "backend" / "config" / "schemas"
    prompts.mkdir(parents=True)
    schemas.mkdir(parents=True)

    (prompts / "CHAPTERS.md").write_text(CHAPTERS_PROMPT, encoding="utf-8")
    (schemas / "chapters.json").write_text(json.dumps(CHAPTERS_SCHEMA), encoding="utf-8")

    (prompts / "VIDEO_META.md").write_text("Titles for {transcript_text}", encoding="utf-8")
    (schemas / "video_meta.json").write_text(json.dumps({"type": "object"}), encoding="utf-8")
    (tmp_path / "backend" / "config" / "llm_tasks.json").write_text(
        json.dumps(
            {
                "metadata": {
                    "template": "backend/config/prompts/VIDEO_META.md",
                    "schema": "backend/config/schemas/video_meta.json",
                    "result_adapter": "video_metadata",
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    return tmp_path


def write_project(root: Path, transcript="hello world", word_map=True):
    project_dir = root / "projects" / PROJECT_ID
    project_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "project_id": PROJECT_ID,
        "name": "Test Project",
        "created_at": datetime.now().isoformat(),
        "files": {},
        "highlights": [],
        "video_metadata": {"components": [], "top_recommendations": []},
        "settings": {"aspect_ratio": "16:9", "resolution": "1080p"},
        "status": None,
        "step_statuses": {},
    }
    (project_dir / "metadata.json").write_text(json.dumps(metadata))
    (project_dir / "transcription.txt").write_text(transcript, encoding="utf-8")
    if word_map:
        (project_dir / "word_map.csv").write_text(
            "word,start,end\nhello,0.0,0.5\nworld,0.5,1.0\n", encoding="utf-8"
        )
    return project_dir


# --- discovery -------------------------------------------------------------

def test_prompt_file_alone_registers_a_task(config_root):
    tasks = discover_tasks()

    assert "chapters" in tasks
    assert tasks["chapters"].template.name == "CHAPTERS.md"
    assert tasks["chapters"].schema == Path("backend/config/schemas/chapters.json")


def test_overridden_template_is_not_also_auto_registered(config_root):
    tasks = discover_tasks()

    # VIDEO_META.md backs the `metadata` task, so it must not additionally
    # appear as a `video_meta` step.
    assert "metadata" in tasks
    assert "video_meta" not in tasks
    assert tasks["metadata"].result_adapter == "video_metadata"


def test_task_without_schema_reports_where_the_schema_belongs(config_root):
    Path("backend/config/schemas/chapters.json").unlink()

    with pytest.raises(SchemaNotFoundError) as excinfo:
        discover_tasks()["chapters"].load_schema()

    assert "backend/config/schemas/chapters.json" in str(excinfo.value)


# --- pipeline wiring -------------------------------------------------------

def test_discovered_task_becomes_a_pipeline_step(config_root):
    pipeline = {
        "steps": {
            "transcription": {"command": "transcribe", "depends_on": [], "auto_run": True},
            "upload": {"command": "upload", "depends_on": ["transcription"], "auto_run": False},
        },
        "execution_order": ["transcription", "upload"],
    }
    config_path = config_root / "backend" / "config" / "pipeline.json"
    config_path.write_text(json.dumps(pipeline))

    orchestrator = PipelineOrchestrator(config_path=str(config_path), services={})

    # The button row is driven by execution_order, so the step has to land there
    # as well as in `steps`, positioned after the dependency it waits on.
    assert orchestrator.pipeline_config["steps"]["chapters"]["depends_on"] == ["transcription"]
    assert orchestrator.pipeline_config["steps"]["chapters"]["auto_run"] is False
    order = orchestrator.pipeline_config["execution_order"]
    assert order.index("chapters") == order.index("transcription") + 1


def test_llm_steps_are_flagged_for_the_ui(config_root):
    pipeline = {
        "steps": {
            "transcription": {"command": "transcribe", "depends_on": [], "auto_run": True},
            "metadata": {"command": "metadata", "depends_on": ["transcription"], "auto_run": True},
        },
        "execution_order": ["transcription", "metadata"],
    }
    config_path = config_root / "backend" / "config" / "pipeline.json"
    config_path.write_text(json.dumps(pipeline))

    steps = PipelineOrchestrator(config_path=str(config_path), services={}).pipeline_config["steps"]

    # Both the step already declared in pipeline.json and the auto-discovered
    # one belong behind the single LLM button.
    assert steps["metadata"]["llm"] is True
    assert steps["chapters"]["llm"] is True
    assert "llm" not in steps["transcription"]


def test_each_discovered_task_gets_its_own_service(config_root):
    config_path = config_root / "backend" / "config" / "pipeline.json"
    config_path.write_text(json.dumps({"steps": {}, "execution_order": []}))

    orchestrator = PipelineOrchestrator(config_path=str(config_path))

    assert isinstance(orchestrator.services["chapters"], LLMQuery)
    assert orchestrator.services["chapters"].task_name == "chapters"


# --- prompt rendering ------------------------------------------------------

def test_build_prompt_fills_only_the_placeholders_the_template_asks_for(config_root):
    write_project(config_root)
    project = Project(PROJECT_ID)

    prompt = build_prompt(CHAPTERS_PROMPT, project)

    assert "hello world" in prompt
    assert "0.00\t0.50\thello" in prompt
    # Escaped braces stay literal so the JSON example survives formatting.
    assert '"chapters": []' in prompt


def test_build_prompt_rejects_unknown_placeholder(config_root):
    write_project(config_root)
    project = Project(PROJECT_ID)

    with pytest.raises(ValueError) as excinfo:
        build_prompt("Summarize {nonsense}", project)

    assert "nonsense" in str(excinfo.value)
    assert "transcript_text" in str(excinfo.value)


# --- schema enforcement ----------------------------------------------------

def test_missing_schema_fails_the_step(config_root):
    write_project(config_root)
    Path("backend/config/schemas/chapters.json").unlink()
    project = Project(PROJECT_ID)

    result = asyncio.run(LLMQuery(task_name="chapters").execute(project))

    assert result["status"] == "error"
    assert Project(PROJECT_ID).step_statuses["chapters"] == "error"


def test_output_violating_schema_fails_the_step(config_root, monkeypatch):
    write_project(config_root)
    project = Project(PROJECT_ID)

    monkeypatch.setattr(
        "backend.src.services.llm_query.LocalCredentialProvider.load", lambda self, key: "test-key"
    )

    class StubClient:
        def __init__(self, *args, **kwargs):
            pass

        def generate_content(self, prompt, is_json=True):
            return json.dumps({"chapters": [{"chapter_time": "00:00:00"}]})

    monkeypatch.setattr("backend.src.services.llm_query.GeminiClient", StubClient)

    result = asyncio.run(LLMQuery(task_name="chapters").execute(project))

    assert result["status"] == "error"
    assert "chapter_title" in result["message"]
    assert Project(PROJECT_ID).step_statuses["chapters"] == "error"


def test_valid_output_lands_in_the_generic_bucket(config_root, monkeypatch):
    write_project(config_root)
    project = Project(PROJECT_ID)
    payload = {"chapters": [{"chapter_time": "00:00:00", "chapter_title": "Intro"}]}

    monkeypatch.setattr(
        "backend.src.services.llm_query.LocalCredentialProvider.load", lambda self, key: "test-key"
    )

    class StubClient:
        def __init__(self, *args, **kwargs):
            pass

        def generate_content(self, prompt, is_json=True):
            return json.dumps(payload)

    monkeypatch.setattr("backend.src.services.llm_query.GeminiClient", StubClient)

    result = asyncio.run(LLMQuery(task_name="chapters").execute(project))

    assert result["status"] == "completed"
    reloaded = Project(PROJECT_ID)
    assert reloaded.llm_outputs["chapters"] == payload
    assert reloaded.step_statuses["chapters"] == "completed"


# --- shipped config --------------------------------------------------------

REPO_CONFIG = Path(__file__).resolve().parents[1] / "config"


def test_shipped_prompts_all_have_a_schema():
    tasks = discover_tasks(
        prompts_dir=REPO_CONFIG / "prompts",
        schemas_dir=REPO_CONFIG / "schemas",
        config_path=REPO_CONFIG / "llm_tasks.json",
    )

    assert {"highlights", "metadata", "chapters"} <= set(tasks)
    # A prompt shipped without its schema would only fail at run time, on the
    # user's click, so it is caught here instead.
    for name, task in tasks.items():
        assert task.load_schema(), f"task '{name}' has an empty schema"


REPO_ROOT = REPO_CONFIG.parents[1]


def shipped_tasks():
    return discover_tasks(
        prompts_dir=REPO_CONFIG / "prompts",
        schemas_dir=REPO_CONFIG / "schemas",
        config_path=REPO_CONFIG / "llm_tasks.json",
    )


def shipped_template(name: str) -> str:
    """The prompt text, read regardless of the working directory.

    llm_tasks.json names its files relative to the repo root, and these tests
    run from a temporary project tree.
    """
    return (REPO_ROOT / shipped_tasks()[name].template).read_text(encoding="utf-8")


def shipped_schema(name: str) -> dict:
    return json.loads((REPO_ROOT / shipped_tasks()[name].schema).read_text(encoding="utf-8"))


def last_json_object(text: str) -> dict:
    """The trailing JSON example a prompt shows the model."""
    end = text.rindex("}")
    depth = 0
    for index in range(end, -1, -1):
        if text[index] == "}":
            depth += 1
        elif text[index] == "{":
            depth -= 1
            if depth == 0:
                return json.loads(text[index:end + 1])
    raise AssertionError("prompt has no balanced JSON example")


@pytest.mark.parametrize("name", sorted(shipped_tasks()))
def test_shipped_prompt_renders(name, config_root):
    write_project(config_root)
    project = Project(PROJECT_ID)

    prompt = build_prompt(shipped_template(name), project)

    # The JSON example a prompt carries is text, not a set of placeholders, so
    # rendering must leave its braces alone rather than fail on them.
    assert "hello world" in prompt
    assert "{transcript_text}" not in prompt


@pytest.mark.parametrize("name", sorted(shipped_tasks()))
def test_shipped_prompt_example_matches_its_schema(name, config_root):
    """The shape a prompt asks for and the shape its schema accepts must agree.

    Otherwise every run of the task is a paid-for API call that fails
    validation.
    """
    write_project(config_root)
    example = last_json_object(build_prompt(shipped_template(name), Project(PROJECT_ID)))

    assert validate(example, shipped_schema(name)) == []


def test_metadata_response_lands_in_typed_fields():
    """A response in the shape VIDEO_META.md asks for survives the adapter."""
    response = {
        "summary": "Two sentences about the video.",
        "titles": [
            {
                "title": f"Title {i}",
                "post_for_x": "x post",
                "post_for_reddit": "reddit post",
                "post_for_linkedin": "linkedin post",
            }
            for i in range(10)
        ],
        "top_2": [
            {"index": 0, "reason": "strongest curiosity gap"},
            {"index": 3, "reason": "clearest promise"},
        ],
    }

    assert validate(response, shipped_schema("metadata")) == []

    metadata = VideoMetadata.from_llm(response)

    assert [c.title for c in metadata.components] == [f"Title {i}" for i in range(10)]
    # The summary is written once by the prompt and the reasons are attached to
    # the two titles they point at.
    assert metadata.components[0].summary == "Two sentences about the video."
    assert metadata.components[0].reason == "strongest curiosity gap"
    assert metadata.components[3].reason == "clearest promise"
    assert metadata.components[1].reason == ""
    assert metadata.components[4].index == 4
    assert len(metadata.top_recommendations) == 2
    # The stored shape has to round-trip through metadata.json.
    assert VideoComponent(**metadata.to_dict()["components"][0]) == metadata.components[0]


def test_metadata_accepts_the_previous_prompt_shape():
    metadata = VideoMetadata.from_llm({
        "components": [{
            "index": 0,
            "title": "Old title",
            "summary": "Old summary",
            "post_for_x": "x",
            "post_for_reddit": "r",
            "post_for_linkedin": "l",
            "reason": "why",
        }],
        "top_recommendations": [{"index": 0, "reason": "why"}],
    })

    assert metadata.components[0].title == "Old title"
    assert metadata.components[0].summary == "Old summary"
    assert metadata.top_recommendations == [{"index": 0, "reason": "why"}]


# --- validator -------------------------------------------------------------

def test_validator_reports_path_of_each_violation():
    errors = validate({"chapters": [{"chapter_time": 12}]}, CHAPTERS_SCHEMA)

    assert any("$.chapters[0].chapter_time" in e and "string" in e for e in errors)
    assert any("chapter_title" in e for e in errors)


def test_validator_accepts_valid_document():
    assert validate({"chapters": [{"chapter_time": "00:00", "chapter_title": "Intro"}]}, CHAPTERS_SCHEMA) == []


def test_validator_does_not_accept_bool_as_number():
    assert validate(True, {"type": "number"})
