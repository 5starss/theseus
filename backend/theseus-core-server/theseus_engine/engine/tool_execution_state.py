"""Tool execution state helpers shared by QueryEngine services."""

from __future__ import annotations

from typing import Any


REMOTE_WORKSPACE_TOOL_NAMES = frozenset(
    {
        "remote_read_file",
        "remote_glob",
        "remote_grep",
        "remote_tail_log",
        "remote_check_cpu",
        "remote_check_memory",
        "remote_check_disk",
        "remote_write_file",
        "remote_edit_file",
        "remote_run_command",
    }
)


def is_remote_workspace_tool(
    tool_metadata: dict[str, Any] | None,
    tool_name: str,
) -> bool:
    return (
        isinstance(tool_metadata, dict)
        and tool_metadata.get("remote_workspace") is not None
        and tool_name in REMOTE_WORKSPACE_TOOL_NAMES
    )
