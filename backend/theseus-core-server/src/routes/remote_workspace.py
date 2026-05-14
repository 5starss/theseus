import asyncio
import logging

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from src.config import settings
from src.remote_workspace.exceptions import RemoteWorkspaceError
from src.remote_workspace.resolver import RemoteWorkspaceResolveError, resolve_remote_workspace_config
from src.remote_workspace.ssh_connector import SshRemoteWorkspaceConnector

logger = logging.getLogger(__name__)
router = APIRouter()


class RemoteWorkspaceConnectionTestRequest(BaseModel):
    """Remote Workspace connection test request from API Server."""

    model_config = ConfigDict(populate_by_name=True)

    project_id: int = Field(alias="projectId")
    remote_workspace_id: int = Field(alias="remoteWorkspaceId")


class RemoteWorkspaceConnectionTestResponse(BaseModel):
    """Remote Workspace SSH connection test result."""

    remote_workspace_id: int
    available: bool
    message: str


@router.post(
    "/remote-workspaces/test-connection",
    response_model=RemoteWorkspaceConnectionTestResponse,
)
async def test_remote_workspace_connection(
    request: RemoteWorkspaceConnectionTestRequest,
    internal_api_key: str | None = Header(default=None, alias="X-Internal-Api-Key"),
) -> RemoteWorkspaceConnectionTestResponse:
    """Verify that Core can reach the Remote Workspace basePath through SSH."""

    if internal_api_key != settings.SPRING_BOOT_INTERNAL_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal API key.",
        )

    logger.info(
        "Remote Workspace connection test started. project=%s workspace=%s",
        request.project_id,
        request.remote_workspace_id,
    )
    try:
        config = await resolve_remote_workspace_config(
            project_id=request.project_id,
            remote_workspace_id=request.remote_workspace_id,
        )
        if config is None:
            raise RemoteWorkspaceResolveError("Remote Workspace config was not resolved.")

        connector = SshRemoteWorkspaceConnector(config)
        result = await asyncio.to_thread(
            connector.run_command,
            "pwd",
            working_directory=".",
            timeout_seconds=10,
        )
        if result.exit_code != 0:
            return RemoteWorkspaceConnectionTestResponse(
                remote_workspace_id=request.remote_workspace_id,
                available=False,
                message=result.stderr.strip() or "Remote Workspace basePath check failed.",
            )

        return RemoteWorkspaceConnectionTestResponse(
            remote_workspace_id=request.remote_workspace_id,
            available=True,
            message="Remote Workspace connection succeeded.",
        )
    except RemoteWorkspaceResolveError as exc:
        logger.info(
            "Remote Workspace config resolve failed. workspace=%s reason=%s",
            request.remote_workspace_id,
            type(exc).__name__,
        )
        return RemoteWorkspaceConnectionTestResponse(
            remote_workspace_id=request.remote_workspace_id,
            available=False,
            message=str(exc),
        )
    except RemoteWorkspaceError as exc:
        logger.info(
            "Remote Workspace connection test failed. workspace=%s reason=%s",
            request.remote_workspace_id,
            type(exc).__name__,
        )
        return RemoteWorkspaceConnectionTestResponse(
            remote_workspace_id=request.remote_workspace_id,
            available=False,
            message=str(exc),
        )
    except Exception as exc:
        logger.warning(
            "Remote Workspace connection test failed unexpectedly. workspace=%s",
            request.remote_workspace_id,
            exc_info=True,
        )
        return RemoteWorkspaceConnectionTestResponse(
            remote_workspace_id=request.remote_workspace_id,
            available=False,
            message="Remote Workspace connection test failed.",
        )
