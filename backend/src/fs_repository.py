import os
import shutil
import json
import threading
from dataclasses import asdict, is_dataclass
from typing import Dict, Any, List
from backend.src.repository import StorageRepository

class FileSystemRepository(StorageRepository):
    def __init__(self):
        self._lock = threading.Lock()

    def exists(self, path: str) -> bool:
        return os.path.exists(path)

    def read_json(self, path: str) -> Dict[str, Any]:
        with open(path, "r") as f:
            return json.load(f)

    def write_json(self, path: str, data: Dict[str, Any]) -> None:
        temp_path = f"{path}.tmp"
        with self._lock:
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(temp_path, path)

    def save_object(self, path: str, obj: Any) -> None:
        """Serialize and save an object (dataclass or dict) to JSON."""
        data = asdict(obj) if is_dataclass(obj) else obj
        
        # Helper to convert nested datetimes to ISO format if present
        def json_serial(obj):
            if hasattr(obj, 'isoformat'):
                return obj.isoformat()
            raise TypeError(f"Type {type(obj)} not serializable")

        temp_path = f"{path}.tmp"
        with self._lock:
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2, default=json_serial)
            os.replace(temp_path, path)

    def delete(self, path: str) -> None:
        if os.path.exists(path):
            os.remove(path)

    def delete_dir(self, path: str) -> None:
        if os.path.exists(path):
            shutil.rmtree(path)

    def list_dirs(self, path: str) -> List[str]:
        if not os.path.exists(path):
            return []
        return [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]
