import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class SettingsManager:
    def __init__(self, config_path: str = "backend/config/settings.json"):
        self.config_path = Path(config_path)
        # Initialization logic separated for easier testing/mocking
        self.settings = self._initialize_and_load()

    def _initialize_and_load(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            defaults = {
                "gemini_api_key": "",
                "youtube_client_secrets": None,
                "theme": "light",
                "pipeline_defaults": {}
            }
            self._save_settings(defaults)
            return defaults
        return self._load_settings()

    def _load_settings(self) -> Dict[str, Any]:
        """Loads settings from the JSON file."""
        if not self.config_path.exists() or self.config_path.stat().st_size == 0:
            return {}
        try:
            with open(self.config_path, "r") as f:
                content = json.load(f)
                return content if content else {}
        except json.JSONDecodeError as e:
            logger.error(f"Error loading settings from {self.config_path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error loading settings from {self.config_path}: {e}")
            return {}

    def _save_settings(self, settings: Dict[str, Any]):
        """Saves settings to the JSON file."""
        try:
            with open(self.config_path, "w") as f:
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

settings_manager = SettingsManager()
