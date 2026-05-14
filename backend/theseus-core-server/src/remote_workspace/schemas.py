from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    @field_validator("host", "username", "base_path")
    @classmethod
    def reject_blank_value(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("value must not be blank")
        return value.strip()

    @field_validator("port")
    @classmethod
    def validate_port(cls, value: int) -> int:
        if value <= 0 or value > 65535:
            raise ValueError("port must be between 1 and 65535")
        return value


class RemoteCommandResult(BaseModel):
    """Result of one SSH command execution."""

    command: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
