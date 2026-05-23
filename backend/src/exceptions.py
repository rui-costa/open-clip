class ProjectError(Exception):
    """Base exception for projects service."""
    pass

class ProjectNotFoundError(ProjectError):
    """Raised when a project is not found."""
    pass
