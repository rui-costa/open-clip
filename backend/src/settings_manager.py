import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class SettingsManager:
    SETTINGS_PATH = Path("backend/config/settings.json")

    def __init__(self, config_path: str = None):
        """Initialize SettingsManager.
        The config_path argument is retained for backward compatibility but ignored.
        The actual path used is the class attribute SETTINGS_PATH
        """
        self.settings = self._initialize_and_load()

    def _initialize_and_load(self) -> Dict[str, Any]:
        """Load settings from the JSON file, creating defaults if missing."""
        path = self.SETTINGS_PATH
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            defaults = {
                "gemini_api_key": "",
                "youtube_client_secrets": None,
                "theme": "light",
                "pipeline_defaults": {},
                "video_defaults": {
                    "resolution": "keep original",
                    "aspect_ratio": "keep original",
                },
            }
            self._save_settings(defaults)
            return defaults
        return self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        """Loads settings from the JSON file."""
        path = self.SETTINGS_PATH
        if not path.exists() or path.stat().st_size == 0:
            return {}
        try:
            with open(path, "r") as f:
                content = json.load(f)
                return content if content else {}
        except json.JSONDecodeError as e:
            logger.error(f"Error loading settings from {path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error loading settings from {path}: {e}")
            return {}

    def _save_settings(self, settings: Dict[str, Any]):
        """Saves settings to the JSON file."""
        path = self.SETTINGS_PATH
        # Ensure parent directories exist
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "w") as f:
                json.dump(settings, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving settings: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a specific setting value."""
        return self.settings.get(key, default)

    def set(self, key: str, value: Any):
        """Updates a specific setting value and persists it."""
        self.settings[key] = value
        self._save_settings(self.settings)

    def update_batch(self, updates: Dict[str, Any]):
        """Updates multiple settings at once and persists them."""
        self.settings.update(updates)
        self._save_settings(self.settings)

    def get_all(self) -> Dict[str, Any]:
        """Returns all current settings."""
        return self.settings

    def get_settings_path(self) -> Path:
        """Utility for tests to retrieve the actual settings file path."""
        return self.SETTINGS_PATH

# Global instance used by the codebase
settings_manager = SettingsManager()
