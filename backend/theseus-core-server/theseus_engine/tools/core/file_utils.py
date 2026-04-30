"""Common file utilities for Theseus tools."""

from pathlib import Path
from typing import Optional

def _resolve_path(base: Path, candidate: str) -> Path:
    """Safely resolve a path relative to the working directory."""
    path = Path(candidate).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()

def _check_path_security(path: Path, cwd: Path) -> Optional[str]:
    """Verify that the path is within the project root (CWD)."""
    try:
        # Check if path is under CWD
        path.relative_to(cwd)
        return None
    except ValueError:
        return f"Security Violation: Path '{path}' is outside the workspace root '{cwd}'."
