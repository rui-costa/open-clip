import pytest
from unittest.mock import MagicMock
from backend.src.project import Project
from backend.src.infrastructure.whisper_client import WhisperClient
from backend.src.infrastructure.gemini_client import GeminiClient
from pathlib import Path
import json

GOLDEN_PROJECT_ID = "00000000-0000-0000-0000-000000000000"
GOLDEN_PROJECT_PATH = Path("projects") / GOLDEN_PROJECT_ID

@pytest.fixture
def golden_project():
    """Load the golden project from disk to act as the source of truth."""
    metadata_path = GOLDEN_PROJECT_PATH / "metadata.json"
    with open(metadata_path, 'r') as f:
        data = json.load(f)
    return Project.from_dict(data)

@pytest.fixture
def project_factory(golden_project):
    """Factory to generate the standard test project, which is the golden source."""
    return golden_project

@pytest.fixture
def credential_provider_mock():
    mock = MagicMock()
    mock.load.return_value = None
    return mock

@pytest.fixture
def whisper_client_mock():
    """Provides a mocked WhisperClient."""
    mock = MagicMock(spec=WhisperClient)
    mock.transcribe.return_value = {
        "text": "hello world",
        "segments": [{"words": [{"word": "hello", "start": 0.1, "end": 0.5}]}]
    }
    return mock

# --- Fake GeminiClient for LLMTaskExecutor tests ---
class FakeGeminiClient:
    def __init__(self, responses=None):
        self.responses = responses or {}
        self.call_args = []

    def generate_content(self, prompt: str, is_json: bool = True) -> str:
        self.call_args.append({'prompt': prompt, 'is_json': is_json})
        return self.responses.get(prompt, '{"highlights": []}' if is_json else "")

@pytest.fixture
def fake_gemini_client():
    """Provides a fake GeminiClient for LLMTaskExecutor tests."""
    return FakeGeminiClient()
