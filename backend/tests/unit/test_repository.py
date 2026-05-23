import pytest
from backend.src.repository import StorageRepository

class MockRepo(StorageRepository):
    def exists(self, path): return True
    def read_json(self, path): return {}
    def write_json(self, path, data): pass
    def delete(self, path): pass
    def delete_dir(self, path): pass
    def save_object(self, path, obj): pass
    def list_dirs(self, path): return []

def test_repo_interface():
    repo = MockRepo()
    assert repo.exists("test") is True
    assert repo.read_json("test") == {}
