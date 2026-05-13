from __future__ import annotations

import logging
import posixpath
import shlex
import socket
from pathlib import Path
from typing import Callable

import paramiko

from src.remote_workspace.exceptions import (
    RemoteWorkspaceAuthenticationError,
    RemoteWorkspaceCommandError,
    RemoteWorkspaceCommandTimeoutError,
    RemoteWorkspaceConnectionError,
    RemoteWorkspacePathError,
)
from src.remote_workspace.schemas import RemoteCommandResult, RemoteWorkspaceConnectionConfig

logger = logging.getLogger(__name__)

DEFAULT_CONNECT_TIMEOUT_SECONDS = 10
DEFAULT_COMMAND_TIMEOUT_SECONDS = 30


class SshRemoteWorkspaceConnector:
    """Creates SSH sessions and executes guarded commands in a Remote Workspace."""

    def __init__(
        self,
        config: RemoteWorkspaceConnectionConfig,
        *,
        client_factory: Callable[[], paramiko.SSHClient] | None = None,
        connect_timeout_seconds: int = DEFAULT_CONNECT_TIMEOUT_SECONDS,
        command_timeout_seconds: int = DEFAULT_COMMAND_TIMEOUT_SECONDS,
    ) -> None:
        self.config = config
        self.client_factory = client_factory or paramiko.SSHClient
        self.connect_timeout_seconds = connect_timeout_seconds
        self.command_timeout_seconds = command_timeout_seconds
        self.base_path = self._normalize_absolute_path(config.base_path)

    def connect(self) -> paramiko.SSHClient:
        """Open an SSH connection using password or private key authentication."""

        client = self.client_factory()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            client.connect(
                hostname=self.config.host,
                port=self.config.port,
                username=self.config.username,
                password=self.config.password,
                pkey=self._load_private_key(),
                timeout=self.connect_timeout_seconds,
                banner_timeout=self.connect_timeout_seconds,
                auth_timeout=self.connect_timeout_seconds,
                look_for_keys=False,
                allow_agent=False,
            )
        except RemoteWorkspaceAuthenticationError:
            raise
        except Exception as exc:
            self._safe_close(client)
            raise RemoteWorkspaceConnectionError(
                f"Failed to connect to remote workspace {self._workspace_label()}."
            ) from exc

        logger.info(
            ">>>> Remote Workspace SSH connection established. workspace=%s host=%s user=%s",
            self._workspace_label(),
            self.config.host,
            self.config.username,
        )
        return client

    def run_command(
        self,
        command: str,
        *,
        working_directory: str | None = None,
        timeout_seconds: int | None = None,
    ) -> RemoteCommandResult:
        """Run a command under the configured base path and return separated output streams."""

        if not command or not command.strip():
            raise RemoteWorkspaceCommandError("Remote command must not be blank.")

        timeout = timeout_seconds or self.command_timeout_seconds
        cwd = self.resolve_path(working_directory or ".")
        guarded_command = f"cd {shlex.quote(cwd)} && {command}"

        logger.info(
            ">>>> Remote Workspace command started. workspace=%s cwd=%s timeoutSeconds=%s",
            self._workspace_label(),
            cwd,
            timeout,
        )

        client = self.connect()
        try:
            _, stdout, stderr = client.exec_command(
                guarded_command,
                timeout=timeout,
                get_pty=False,
            )
            exit_code = stdout.channel.recv_exit_status()
            stdout_text = stdout.read().decode("utf-8", errors="replace")
            stderr_text = stderr.read().decode("utf-8", errors="replace")
            logger.info(
                ">>>> Remote Workspace command finished. workspace=%s exitCode=%s",
                self._workspace_label(),
                exit_code,
            )
            return RemoteCommandResult(
                command=command,
                exit_code=exit_code,
                stdout=stdout_text,
                stderr=stderr_text,
            )
        except socket.timeout as exc:
            raise RemoteWorkspaceCommandTimeoutError(
                f"Remote command exceeded {timeout} seconds."
            ) from exc
        except RemoteWorkspaceCommandTimeoutError:
            raise
        except Exception as exc:
            raise RemoteWorkspaceCommandError(
                f"Remote command execution failed for workspace {self._workspace_label()}."
            ) from exc
        finally:
            self._safe_close(client)

    def resolve_path(self, requested_path: str) -> str:
        """Resolve a remote path and reject access outside basePath."""

        if not requested_path or not requested_path.strip():
            return self.base_path

        raw_path = requested_path.strip()
        if posixpath.isabs(raw_path):
            candidate = self._normalize_absolute_path(raw_path)
        else:
            candidate = self._normalize_absolute_path(posixpath.join(self.base_path, raw_path))

        if not self._is_under_base_path(candidate):
            raise RemoteWorkspacePathError(
                f"Remote path escapes basePath. workspace={self._workspace_label()}"
            )
        return candidate

    def _load_private_key(self) -> paramiko.PKey | None:
        if not self.config.private_key_path:
            if not self.config.password:
                raise RemoteWorkspaceAuthenticationError(
                    "Remote Workspace requires password or privateKeyPath."
                )
            return None

        key_path = Path(self.config.private_key_path).expanduser()
        key_loaders = (
            paramiko.RSAKey.from_private_key_file,
            paramiko.ECDSAKey.from_private_key_file,
            paramiko.Ed25519Key.from_private_key_file,
            paramiko.DSSKey.from_private_key_file,
        )
        last_error: Exception | None = None
        for loader in key_loaders:
            try:
                return loader(str(key_path), password=self.config.password)
            except Exception as exc:
                last_error = exc
        raise RemoteWorkspaceAuthenticationError(
            f"Failed to load private key for remote workspace {self._workspace_label()}."
        ) from last_error

    def _normalize_absolute_path(self, path: str) -> str:
        normalized = posixpath.normpath(path.strip())
        if not posixpath.isabs(normalized):
            raise RemoteWorkspacePathError("Remote basePath must be an absolute path.")
        return normalized

    def _is_under_base_path(self, path: str) -> bool:
        if self.base_path == "/":
            return True
        return path == self.base_path or path.startswith(f"{self.base_path}/")

    def _workspace_label(self) -> str:
        return str(self.config.remote_workspace_id or self.config.name or self.config.host)

    def _safe_close(self, client: paramiko.SSHClient) -> None:
        try:
            client.close()
        except Exception:
            logger.debug("Remote Workspace SSH client close failed.", exc_info=True)
