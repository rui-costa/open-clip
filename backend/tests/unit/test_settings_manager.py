import pytest
import io
from unittest.mock import patch, MagicMock
from backend.src.settings_manager import SettingsManager

@pytest.fixture
def manager():
    mock_data = {"gemini_api_key": "", "theme": "light"}
    mock_json = '{"gemini_api_key": "", "theme": "light"}'
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.stat", return_value=MagicMock(st_size=len(mock_json))), \
         patch("builtins.open", return_value=io.StringIO(mock_json)):
        m = SettingsManager(config_path="mock_settings.json")
        m.settings = mock_data.copy()
        return m

def test_settings_persistence(manager):
    with patch("builtins.open"), patch("json.dump"):
        manager.set("test_key", "test_value")
        assert manager.settings["test_key"] == "test_value"

def test_batch_update(manager):
    with patch("builtins.open"), patch("json.dump"):
        updates = {"key1": "val1", "key2": "val2"}
        manager.update_batch(updates)
        assert manager.settings["key1"] == "val1"
        assert manager.settings["key2"] == "val2"

def test_default_values(manager):
    assert "gemini_api_key" in manager.get_all()
    assert manager.get("theme") == "light"

# Tests for SettingsManager behavior
import json
import os
import pathlib
import pytest
from unittest import mock

from backend.src.settings_manager import settings_manager

@pytest.fixture
def temp_settings_file(tmp_path):
    # Create a temporary settings.json file
    settings_path = tmp_path / "settings.json"
    # Write default empty JSON
    settings_path.write_text(json.dumps({}))
    # Patch the SETTINGS_PATH in the module
    with mock.patch.object(settings_manager, "SETTINGS_PATH", settings_path):
        yield settings_path

def test_load_default_when_missing(temp_settings_file, monkeypatch):
    # Ensure file does not exist
    temp_settings_file.unlink()
    # Reload settings_manager (force reload)
    import importlib
    import backend.src.settings_manager as sm_mod
    importlib.reload(sm_mod)
    # Should load defaults (empty dict)
    assert sm_mod.settings_manager.get("nonexistent") is None

def test_update_and_get_batch(temp_settings_file):
    # Update multiple keys
    settings_manager.update_batch({"api_key": "123", "model": "gpt"})
    assert settings_manager.get("api_key") == "123"
    assert settings_manager.get("model") == "gpt"
    # Ensure persisted to file
    data = json.loads(temp_settings_file.read_text())
    assert data["api_key"] == "123"
    assert data["model"] == "gpt"

def test_set_and_get_individual(temp_settings_file):
    settings_manager.set("new_key", "value")
    assert settings_manager.get("new_key") == "value"
    # Verify file content
    data = json.loads(temp_settings_file.read_text())
    assert data["new_key"] == "value"
