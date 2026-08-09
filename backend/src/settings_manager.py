import json
import logging
import os
from pathlib import Path
from typing import Dict, Any, Optional

from backend.src.infrastructure.credentials import LocalCredentialProvider

logger = logging.getLogger(__name__)

SECRET_KEYS = {"gemini_api_key", "youtube_client_secrets"}

def is_secret_key(key: str) -> bool:
    return key in SECRET_KEYS or key.endswith("_key") or key.endswith("_secret") or key.endswith("_secrets")

class SettingsManager:
    SETTINGS_PATH = Path("backend/config/settings.json")

    def __init__(self, config_path: str = None):
        """Initialize SettingsManager.
        The config_path argument is retained for backward compatibility but ignored.
        The actual path used is the class attribute SETTINGS_PATH
        """
        self.settings = self._initialize_and_load()

    def _get_credential_provider(self) -> LocalCredentialProvider:
        secrets_dir = str(self.SETTINGS_PATH.parent)
        return LocalCredentialProvider(secrets_dir=secrets_dir)

    def _initialize_and_load(self) -> Dict[str, Any]:
        """Load settings from the JSON file, creating defaults if missing."""
        path = self.SETTINGS_PATH
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            defaults = {
                "theme": "light",
                "log_level": "INFO",
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
        """Loads settings from the JSON file, stripping and migrating any secret keys."""
        path = self.SETTINGS_PATH
        if not path.exists() or path.stat().st_size == 0:
            return {}
        try:
            with open(path, "r") as f:
                content = json.load(f)
                settings = content if isinstance(content, dict) else {}
        except json.JSONDecodeError as e:
            logger.error(f"Error loading settings from {path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Unexpected error loading settings from {path}: {e}")
            return {}

        # Check if any secret keys exist in settings.json
        secrets_found = {k: v for k, v in settings.items() if is_secret_key(k)}
        if secrets_found:
            provider = self._get_credential_provider()
            existing_secrets = provider.load_all()
            for k, v in secrets_found.items():
                if k not in existing_secrets:
                    provider.save(k, v)
                del settings[k]
            self._save_settings(settings)

        return settings

    def _save_settings(self, settings: Dict[str, Any]):
        """Saves non-secret settings to the JSON file."""
        path = self.SETTINGS_PATH
        # Filter out any secret keys just in case
        clean_settings = {k: v for k, v in settings.items() if not is_secret_key(k)}
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(path, "w") as f:
                json.dump(clean_settings, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving settings: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a specific setting or secret value."""
        if is_secret_key(key):
            val = self._get_credential_provider().load(key)
            return val if val is not None else default
        return self.settings.get(key, default)

    def set(self, key: str, value: Any):
        """Updates a specific setting or secret value and persists it."""
        if is_secret_key(key):
            self._get_credential_provider().save(key, value)
            if key in self.settings:
                del self.settings[key]
                self._save_settings(self.settings)
        else:
            self.settings[key] = value
            self._save_settings(self.settings)

    def update_batch(self, updates: Dict[str, Any]):
        """Updates multiple settings at once, routing secrets to secrets.json."""
        logger.info(f"update_batch called with updates: {updates.keys()}")
        secrets_dict = {}
        normals_dict = {}
        for k, v in updates.items():
            if is_secret_key(k):
                secrets_dict[k] = v
            else:
                normals_dict[k] = v

        if secrets_dict:
            self._get_credential_provider().save_all(secrets_dict)
            for k in secrets_dict:
                self.settings.pop(k, None)

        if normals_dict:
            self.settings.update(normals_dict)

        logger.info(f"Saving settings to json: {self.settings.keys()}")
        self._save_settings(self.settings)

    def get_all(self) -> Dict[str, Any]:
        """Returns all current settings, including secrets."""
        all_settings = self.settings.copy()
        secrets = self._get_credential_provider().load_all()
        all_settings.update(secrets)
        return all_settings

    def get_settings_path(self) -> Path:
        """Utility for tests to retrieve the actual settings file path."""
        return self.SETTINGS_PATH

# Global instance used by the codebase
settings_manager = SettingsManager()

