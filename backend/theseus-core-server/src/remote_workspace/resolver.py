from __future__ import annotations

import logging

import httpx
from pydantic import ValidationError

from src.auth.client import internal_api_headers, unwrap_api_response
from src.config import settings
from src.remote_workspace.schemas import RemoteWorkspaceConnectionConfig

logger = logging.getLogger(__name__)


class RemoteWorkspaceResolveError(RuntimeError):
    """Raised when Core cannot resolve a Remote Workspace connection config."""


class RemoteWorkspaceResolver:
    """Resolves SSH connection config from API Server by Remote Workspace id."""

    def __init__(
        self,
        *,
        config_url: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self.config_url = config_url or settings.SPRING_BOOT_REMOTE_WORKSPACE_CONFIG_URL
        self.timeout_seconds = timeout_seconds or settings.INTERNAL_API_TIMEOUT_SECONDS

    async def resolve(
        self,
        *,
        project_id: int | str,
        remote_workspace_id: int,
    ) -> RemoteWorkspaceConnectionConfig:
        payload = {
            "projectId": int(project_id),
            "remoteWorkspaceId": int(remote_workspace_id),
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.config_url,
                    headers=internal_api_headers(),
                    json=payload,
                    timeout=self.timeout_seconds,
                )
            except httpx.RequestError as exc:
                raise RemoteWorkspaceResolveError(
                    "Remote Workspace config resolver is unavailable."
                ) from exc

        if response.status_code != 200:
            logger.warning(
                "Remote Workspace config resolver failed. workspace=%s status=%s",
                remote_workspace_id,
                response.status_code,
            )
            raise RemoteWorkspaceResolveError(
                "Remote Workspace config resolver returned an error."
            )

        try:
            resolved_payload = unwrap_api_response(response.json())
            return RemoteWorkspaceConnectionConfig.model_validate(resolved_payload)
        except (ValueError, ValidationError) as exc:
            raise RemoteWorkspaceResolveError(
                "Remote Workspace config resolver returned invalid data."
            ) from exc


async def resolve_remote_workspace_config(
    *,
    project_id: int | str | None,
    remote_workspace_id: int | None,
    resolver: RemoteWorkspaceResolver | None = None,
) -> RemoteWorkspaceConnectionConfig | None:
    if remote_workspace_id is None:
        return None
    if project_id is None:
        raise RemoteWorkspaceResolveError("Remote Workspace resolution requires project id.")

    active_resolver = resolver or RemoteWorkspaceResolver()
    return await active_resolver.resolve(
        project_id=project_id,
        remote_workspace_id=remote_workspace_id,
    )
