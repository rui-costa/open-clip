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

