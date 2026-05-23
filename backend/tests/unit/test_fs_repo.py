import pytest
import json
import os
from backend.src.fs_repository import FileSystemRepository

@pytest.fixture
def repo(tmp_path):
    return FileSystemRepository()

def test_fs_repo_operations(repo, tmp_path):
    file_path = tmp_path / "test.json"
    data = {"key": "value"}
    
    repo.write_json(str(file_path), data)
    assert repo.exists(str(file_path))
    assert repo.read_json(str(file_path)) == data
    
    repo.delete(str(file_path))
    assert not repo.exists(str(file_path))

def test_list_dirs(repo, tmp_path):
    (tmp_path / "dir1").mkdir()
    (tmp_path / "dir2").mkdir()
    (tmp_path / "file.txt").write_text("content")
    
    dirs = repo.list_dirs(str(tmp_path))
    assert "dir1" in dirs
    assert "dir2" in dirs
    assert "file.txt" not in dirs
