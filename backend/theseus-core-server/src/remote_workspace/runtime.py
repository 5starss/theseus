from __future__ import annotations

from typing import Any

from src.remote_workspace.schemas import RemoteCommandResult, RemoteWorkspaceConnectionConfig
from src.remote_workspace.ssh_connector import SshRemoteWorkspaceConnector

DEFAULT_REMOTE_RUNTIME_TIMEOUT_SECONDS = 180


class RemoteWorkspaceRuntimeError(RuntimeError):
    """Raised when a generated Tool cannot use the selected Remote Workspace."""


def get_remote_workspace_config(context: Any) -> RemoteWorkspaceConnectionConfig | None:
    """Return the Remote Workspace config carried by a Tool execution context."""

    metadata = getattr(context, "metadata", None)
    if not isinstance(metadata, dict):
        return None

    remote_workspace = metadata.get("remote_workspace")
    if remote_workspace is None:
        return None
    if isinstance(remote_workspace, RemoteWorkspaceConnectionConfig):
        return remote_workspace

    try:
        return RemoteWorkspaceConnectionConfig.model_validate(remote_workspace)
    except Exception as exc:
        raise RemoteWorkspaceRuntimeError("Remote Workspace metadata is invalid.") from exc


def require_remote_workspace(context: Any) -> RemoteWorkspaceConnectionConfig:
    """Return the Remote Workspace config or raise a clear runtime error."""

    config = get_remote_workspace_config(context)
    if config is None:
        raise RemoteWorkspaceRuntimeError("Remote Workspace is required to execute this Tool.")
    return config


def run_remote_command(
    context: Any,
    command: str,
    *,
    cwd: str = ".",
    timeout_seconds: int = DEFAULT_REMOTE_RUNTIME_TIMEOUT_SECONDS,
) -> RemoteCommandResult:
    """Execute a command in the selected Remote Workspace."""

    if timeout_seconds <= 0:
        raise RemoteWorkspaceRuntimeError("Remote command timeout must be positive.")

    connector = SshRemoteWorkspaceConnector(require_remote_workspace(context))
    return connector.run_command(
        command,
        working_directory=cwd,
        timeout_seconds=min(timeout_seconds, DEFAULT_REMOTE_RUNTIME_TIMEOUT_SECONDS),
    )
