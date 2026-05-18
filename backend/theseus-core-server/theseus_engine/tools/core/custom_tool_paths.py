from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


_DEFAULT_CUSTOM_TOOLS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "custom_tools")
)
CUSTOM_TOOLS_DIR = os.path.abspath(
    os.getenv("THESEUS_CUSTOM_TOOLS_DIR", "").strip() or _DEFAULT_CUSTOM_TOOLS_DIR
)
PROJECT_CUSTOM_TOOLS_DIR = os.path.abspath(
    os.getenv("THESEUS_PROJECT_CUSTOM_TOOLS_DIR", "").strip()
    or os.path.join(CUSTOM_TOOLS_DIR, "projects")
)


def get_custom_tools_dir() -> str:
    """Return the configured custom tool root directory."""
    return os.path.abspath(
        os.getenv("THESEUS_CUSTOM_TOOLS_DIR", "").strip() or CUSTOM_TOOLS_DIR
    )


def get_project_custom_tools_dir() -> str:
    """Return the configured project custom tool root directory."""
    return os.path.abspath(
        os.getenv("THESEUS_PROJECT_CUSTOM_TOOLS_DIR", "").strip()
        or os.path.join(get_custom_tools_dir(), "projects")
    )


def canonical_tool_module_stem(tool_name: str) -> str:
    """Return the persisted module stem for a logical custom tool name."""
    normalized = tool_name.strip().lower().replace("-", "_")
    if normalized.endswith("_tool"):
        return normalized
    return f"{normalized}_tool"


def custom_tool_dirs(extra_dirs: Optional[list[str | os.PathLike[str]]] = None) -> list[str]:
    """Return custom tool directories in load order, de-duplicated."""
    dirs: list[str] = []
    seen: set[str] = set()
    raw_dirs: list[str | os.PathLike[str]] = [get_custom_tools_dir()]
    env_dir = os.getenv("THESEUS_CUSTOM_TOOLS_DIR", "").strip()
    if env_dir:
        raw_dirs.extend(part.strip() for part in env_dir.split(os.pathsep) if part.strip())
    if extra_dirs:
        raw_dirs.extend(extra_dirs)

    for raw in raw_dirs:
        path = os.path.abspath(os.fspath(raw))
        key = os.path.normcase(path)
        if key in seen:
            continue
        seen.add(key)
        dirs.append(path)
    return dirs


def workspace_custom_tool_dirs(
    cwd: str | os.PathLike[str],
    core_root: str | os.PathLike[str] | None = None,
) -> list[Path]:
    """Return custom tool dirs visible to a local workspace runtime.

    The VSCode extension can run from a repository root while the engine code
    lives under ``backend/theseus-core-server``. Keep this list aligned with the
    extension's host-side preview so the UI does not show tools the runner will
    never load.
    """
    workspace = Path(cwd).resolve()
    candidates: list[Path] = [
        workspace / "custom_tools",
        workspace / "theseus_engine" / "custom_tools",
        workspace / "backend" / "theseus-core-server" / "custom_tools",
        workspace / "backend" / "theseus-core-server" / "theseus_engine" / "custom_tools",
    ]
    configured_core = core_root or os.getenv("THESEUS_CORE_ROOT", "").strip()
    if configured_core:
        core_path = Path(configured_core).resolve()
        candidates.extend([
            core_path / "custom_tools",
            core_path / "theseus_engine" / "custom_tools",
        ])

    seen: set[str] = set()
    result: list[Path] = []
    for candidate in candidates:
        key = os.path.normcase(str(candidate))
        if key in seen:
            continue
        seen.add(key)
        result.append(candidate)
    return result


def project_tool_dir(project_id: str | int | None) -> Path:
    return Path(get_project_custom_tools_dir()) / str(project_id or "local")
