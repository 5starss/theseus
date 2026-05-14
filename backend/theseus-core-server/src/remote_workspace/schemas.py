from __future__ import annotations

import posixpath
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


REMOTE_WORKSPACE_REDACTED_VALUE = "***"
ACTIVE_REMOTE_WORKSPACE_STATUSES = frozenset({"ACTIVE"})


class RemoteWorkspaceConnectionConfig(BaseModel):
    """Core-internal SSH connection information for a Remote Workspace."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    remote_workspace_id: int | None = Field(default=None, alias="remoteWorkspaceId")
    project_id: int | None = Field(default=None, alias="projectId")
    name: str | None = None
    host: str
    port: int = 22
    username: str
    password: str | None = None
    private_key_path: str | None = Field(default=None, alias="privateKeyPath")
    base_path: str = Field(alias="basePath")
    allow_write_execution: bool = Field(default=False, alias="allowWriteExecution")
    status: str | None = None

    @field_validator("password", "private_key_path", mode="before")
    @classmethod
    def normalize_optional_secret(cls, value: object) -> object | None:
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("host", "username", "base_path")
    @classmethod
    def reject_blank_value(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("value must not be blank")
        return value.strip()

    @field_validator("base_path")
    @classmethod
    def validate_base_path(cls, value: str) -> str:
        normalized = posixpath.normpath(value.strip())
        if not posixpath.isabs(normalized):
            raise ValueError("basePath must be an absolute path")
        return normalized

    @field_validator("port")
    @classmethod
    def validate_port(cls, value: int) -> int:
        if value <= 0 or value > 65535:
            raise ValueError("port must be between 1 and 65535")
        return value

    @model_validator(mode="after")
    def validate_core_remote_policy(self) -> "RemoteWorkspaceConnectionConfig":
        status = (self.status or "").strip().upper()
        if status and status not in ACTIVE_REMOTE_WORKSPACE_STATUSES:
            raise ValueError("Remote Workspace status must be ACTIVE")
        if self.base_path == "/":
            raise ValueError("Remote Workspace basePath '/' is not allowed")
        if not self.password and not self.private_key_path:
            raise ValueError("Remote Workspace requires password or privateKeyPath")
        return self

    def redacted_model_dump(self, *, by_alias: bool = True) -> dict[str, Any]:
        """Return metadata-safe config without SSH secrets."""

        payload = self.model_dump(mode="json", by_alias=by_alias)
        private_key_field = "privateKeyPath" if by_alias else "private_key_path"
        payload["password"] = (
            REMOTE_WORKSPACE_REDACTED_VALUE if self.password else None
        )
        payload[private_key_field] = (
            REMOTE_WORKSPACE_REDACTED_VALUE if self.private_key_path else None
        )
        return payload


class RemoteCommandResult(BaseModel):
    """Result of one SSH command execution."""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
