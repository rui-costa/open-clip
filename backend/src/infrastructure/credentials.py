import json
import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class LocalCredentialProvider:
    def __init__(self, secrets_dir: str = "backend/config"):
        self.secrets_file = os.path.join(secrets_dir, "secrets.json")

    def load_all(self) -> Dict[str, Any]:
        if not os.path.exists(self.secrets_file):
            logger.info("Secrets file does not exist.")
            return {}
        try:
            with open(self.secrets_file, "r") as f:
                content = json.load(f)
                logger.info(f"Loaded secrets: {content.keys()}")
                return content if isinstance(content, dict) else {}
        except Exception as e:
            logger.error(f"Error loading secrets: {e}")
            return {}

    def load(self, key: str) -> Optional[Any]:
        secrets = self.load_all()
        return secrets.get(key)

    def save(self, key: str, value: Any) -> None:
        os.makedirs(os.path.dirname(self.secrets_file), exist_ok=True)
        secrets = self.load_all()
        secrets[key] = value
        with open(self.secrets_file, "w") as f:
            json.dump(secrets, f, indent=4)

    def save_all(self, secrets_dict: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.secrets_file), exist_ok=True)
        secrets = self.load_all()
        secrets.update(secrets_dict)
        with open(self.secrets_file, "w") as f:
            json.dump(secrets, f, indent=4)

