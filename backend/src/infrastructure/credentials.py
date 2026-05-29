import os
import json
from typing import Optional, Dict, Any

class LocalCredentialProvider:
    def __init__(self, secrets_dir: str = "backend/config"):
        self.secrets_file = os.path.join(secrets_dir, "secrets.json")

    def load_all(self) -> Dict[str, Any]:
        if not os.path.exists(self.secrets_file):
            return {}
        with open(self.secrets_file, "r") as f:
            return json.load(f)

    def load(self, key: str) -> Optional[Any]:
        secrets = self.load_all()
        return secrets.get(key)

    def save(self, key: str, value: Any) -> None:
        if not os.path.exists(self.secrets_file):
            raise FileNotFoundError(f"Secrets file not found: {self.secrets_file}")
        
        secrets = self.load_all()
        secrets[key] = value
        with open(self.secrets_file, "w") as f:
            json.dump(secrets, f, indent=4)
