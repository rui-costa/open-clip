import os
import json
from typing import Optional, Dict, Any

class LocalCredentialProvider:
    def __init__(self, credentials_dir: str):
        self.credentials_dir = credentials_dir
        os.makedirs(self.credentials_dir, exist_ok=True)
        self.credential_file = os.path.join(self.credentials_dir, "youtube_credentials.json")

    def load(self, name: str) -> Optional[Dict[str, Any]]:
        if os.path.exists(self.credential_file):
            with open(self.credential_file, "r") as f:
                return json.load(f)
        return None

    def save(self, name: str, data: Dict[str, Any]) -> None:
        with open(self.credential_file, "w") as f:
            json.dump(data, f, indent=4)
