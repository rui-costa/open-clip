import shutil
from pathlib import Path
from typing import List

BASE_DIR = Path("projects")

def list_projects() -> List[str]:
    """Returns a list of project IDs in the projects directory."""
    if not BASE_DIR.exists():
        return []
    return [d.name for d in BASE_DIR.iterdir() if d.is_dir()]

def delete_project(project_id: str) -> bool:
    """Deletes a project directory."""
    project_path = BASE_DIR / project_id
    if project_path.exists():
        shutil.rmtree(project_path)
        return True
    return False
