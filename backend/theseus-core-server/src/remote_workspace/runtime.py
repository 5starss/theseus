from __future__ import annotations

from typing import Any
from uuid import uuid4

from src.remote_workspace.schemas import (
    REMOTE_WORKSPACE_REDACTED_VALUE,
    RemoteCommandResult,
    RemoteWorkspaceConnectionConfig,
)
from src.remote_workspace.ssh_connector import SshRemoteWorkspaceConnector

DEFAULT_REMOTE_RUNTIME_TIMEOUT_SECONDS = 180
REMOTE_WORKSPACE_METADATA_KEY = "remote_workspace"
REMOTE_WORKSPACE_RUNTIME_KEY = "remote_workspace_runtime_key"

_RUNTIME_CONFIGS: dict[str, RemoteWorkspaceConnectionConfig] = {}


class RemoteWorkspaceRuntimeError(RuntimeError):
    """Raised when a generated Tool cannot use the selected Remote Workspace."""


def register_remote_workspace_config(config: RemoteWorkspaceConnectionConfig) -> str:
    """Store a private runtime config and return a non-secret lookup key."""

    key = f"rw-{uuid4().hex}"
    _RUNTIME_CONFIGS[key] = config
    return key


def get_remote_workspace_config(context: Any) -> RemoteWorkspaceConnectionConfig | None:
    """Return the Remote Workspace config carried by a Tool execution context."""

    metadata = getattr(context, "metadata", None)
    if not isinstance(metadata, dict):
        return None

    runtime_key = metadata.get(REMOTE_WORKSPACE_RUNTIME_KEY)
    if isinstance(runtime_key, str):
        config = _RUNTIME_CONFIGS.get(runtime_key)
        if config is not None:
            return config

    remote_workspace = metadata.get(REMOTE_WORKSPACE_METADATA_KEY)
    if remote_workspace is None:
        return None
    if isinstance(remote_workspace, RemoteWorkspaceConnectionConfig):
        return remote_workspace
    if (
        isinstance(remote_workspace, dict)
        and (
            remote_workspace.get("password") == REMOTE_WORKSPACE_REDACTED_VALUE
            or remote_workspace.get("privateKeyPath") == REMOTE_WORKSPACE_REDACTED_VALUE
            or remote_workspace.get("private_key_path") == REMOTE_WORKSPACE_REDACTED_VALUE
        )
    ):
        raise RemoteWorkspaceRuntimeError(
            "Remote Workspace metadata is redacted. "
            "Use the Core runtime helper with the provided execution context."
        )

    try:
        return RemoteWorkspaceConnectionConfig.model_validate(remote_workspace)
    except Exception as exc:
        raise RemoteWorkspaceRuntimeError(
            "Remote Workspace metadata is invalid or redacted. "
            "Use the Core runtime helper with the provided execution context."
        ) from exc


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
