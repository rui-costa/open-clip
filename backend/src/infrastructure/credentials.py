import json
import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class JsonFileStore:
    """A flat key/value store backed by a single JSON file."""

    def __init__(self, config_dir: str = "backend/config", filename: str = "store.json"):
        self.path = os.path.join(config_dir, filename)

    def load_all(self) -> Dict[str, Any]:
        if not os.path.exists(self.path):
            logger.info(f"{self.path} does not exist.")
            return {}
        try:
            with open(self.path, "r") as f:
                content = json.load(f)
                logger.info(f"Loaded {self.path}: {list(content.keys()) if isinstance(content, dict) else 'invalid'}")
                return content if isinstance(content, dict) else {}
        except Exception as e:
            logger.error(f"Error loading {self.path}: {e}")
            return {}

    def load(self, key: str) -> Optional[Any]:
        return self.load_all().get(key)

    def save(self, key: str, value: Any) -> None:
        self.save_all({key: value})

    def save_all(self, values: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        stored = self.load_all()
        stored.update(values)
        try:
            with open(self.path, "w") as f:
                json.dump(stored, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving {self.path}: {e}")

    def delete(self, key: str) -> None:
        stored = self.load_all()
        if key not in stored:
            return
        del stored[key]
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        try:
            with open(self.path, "w") as f:
                json.dump(stored, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving {self.path}: {e}")


class LocalCredentialProvider(JsonFileStore):
    """Stores API keys and other credentials in backend/config/secrets.json."""

    def __init__(self, secrets_dir: str = "backend/config"):
        super().__init__(config_dir=secrets_dir, filename="secrets.json")

    @property
    def secrets_file(self) -> str:
        return self.path


class LocalUserSettingsProvider(JsonFileStore):
    """Stores per-user preferences in backend/config/user_settings.json.

    These are the settings that differ between installations - personal
    descriptions, self-hosted service URLs, machine-specific encoders - and are
    kept out of the tracked settings.json so the repository stays shareable.
    """

    def __init__(self, config_dir: str = "backend/config"):
        super().__init__(config_dir=config_dir, filename="user_settings.json")
