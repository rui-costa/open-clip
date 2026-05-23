from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List, TypeVar, Type, Generic

T = TypeVar("T")

class StorageRepository(ABC):
    @abstractmethod
    def exists(self, path: str) -> bool:
        pass

    @abstractmethod
    def read_json(self, path: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def write_json(self, path: str, data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    def delete(self, path: str) -> None:
        pass

    @abstractmethod
    def delete_dir(self, path: str) -> None:
        pass

    @abstractmethod
    def list_dirs(self, path: str) -> List[str]:
        pass

    @abstractmethod
    def save_object(self, path: str, obj: Any) -> None:
        """Serialize and save an object (dataclass or dict) to JSON."""
        pass
