import os
import json
import tempfile
import pytest
from pathlib import Path

from backend.src.settings_manager import SettingsManager, is_secret_key
from backend.src.infrastructure.credentials import LocalCredentialProvider

def test_is_secret_key():
    assert is_secret_key("gemini_api_key") is True
    assert is_secret_key("youtube_client_secrets") is True
    assert is_secret_key("some_other_secret") is True
    assert is_secret_key("theme") is False
    assert is_secret_key("log_level") is False

def test_settings_manager_separates_secrets_and_settings():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        settings_file = config_dir / "settings.json"
        secrets_file = config_dir / "secrets.json"

        # Create custom SettingsManager pointing to tmpdir
        manager = SettingsManager()
        manager.SETTINGS_PATH = settings_file
        manager.settings = manager._initialize_and_load()

        # Update batch with a mix of secrets and normal settings
        manager.update_batch({
            "theme": "dark",
            "log_level": "DEBUG",
            "gemini_api_key": "TEST_GEMINI_KEY_123",
            "youtube_client_secrets": {"installed": {"client_id": "test_id"}}
        })

        # Verify settings.json does NOT contain secrets
        with open(settings_file, "r") as f:
            settings_json = json.load(f)
        assert "theme" in settings_json
        assert settings_json["theme"] == "dark"
        assert "gemini_api_key" not in settings_json
        assert "youtube_client_secrets" not in settings_json

        # Verify secrets.json contains the secrets
        with open(secrets_file, "r") as f:
            secrets_json = json.load(f)
        assert secrets_json["gemini_api_key"] == "TEST_GEMINI_KEY_123"
        assert secrets_json["youtube_client_secrets"] == {"installed": {"client_id": "test_id"}}

        # Verify get() retrieves both normal settings and secrets
        assert manager.get("theme") == "dark"
        assert manager.get("gemini_api_key") == "TEST_GEMINI_KEY_123"
        assert manager.get("youtube_client_secrets") == {"installed": {"client_id": "test_id"}}

        # Verify get_all() combines both
        all_settings = manager.get_all()
        assert all_settings["theme"] == "dark"
        assert all_settings["gemini_api_key"] == "TEST_GEMINI_KEY_123"

def test_settings_manager_migrates_existing_secrets_from_settings_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        settings_file = config_dir / "settings.json"
        secrets_file = config_dir / "secrets.json"

        # Manually create settings.json with a secret in it
        initial_settings = {
            "theme": "light",
            "gemini_api_key": "LEGACY_SECRET_KEY"
        }
        with open(settings_file, "w") as f:
            json.dump(initial_settings, f)

        # Initialize SettingsManager
        manager = SettingsManager()
        manager.SETTINGS_PATH = settings_file
        manager.settings = manager._initialize_and_load()

        # Check that secret was removed from settings.json
        with open(settings_file, "r") as f:
            clean_settings = json.load(f)
        assert "gemini_api_key" not in clean_settings
        assert clean_settings["theme"] == "light"

        # Check that secret was migrated to secrets.json
        with open(secrets_file, "r") as f:
            migrated_secrets = json.load(f)
        assert migrated_secrets["gemini_api_key"] == "LEGACY_SECRET_KEY"
