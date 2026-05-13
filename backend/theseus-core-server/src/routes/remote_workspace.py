import asyncio
import logging

from fastapi import APIRouter
from pydantic import BaseModel

from src.remote_workspace.exceptions import RemoteWorkspaceError
from src.remote_workspace.schemas import RemoteWorkspaceConnectionConfig
from src.remote_workspace.ssh_connector import SshRemoteWorkspaceConnector

logger = logging.getLogger(__name__)
router = APIRouter()


class RemoteWorkspaceConnectionTestResponse(BaseModel):
    """Remote Workspace SSH connection test result."""

    remote_workspace_id: int | None = None
    available: bool
    message: str


@router.post(
    "/remote-workspaces/test-connection",
    response_model=RemoteWorkspaceConnectionTestResponse,
)
async def test_remote_workspace_connection(
    request: RemoteWorkspaceConnectionConfig,
) -> RemoteWorkspaceConnectionTestResponse:
    """Verify that Core can reach the Remote Workspace basePath through SSH."""

    logger.info(
        "Remote Workspace connection test started. workspace=%s host=%s",
        request.remote_workspace_id or request.name or request.host,
        request.host,
    )
    try:
        connector = SshRemoteWorkspaceConnector(request)
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
    except RemoteWorkspaceError as exc:
        logger.info(
            "Remote Workspace connection test failed. workspace=%s reason=%s",
            request.remote_workspace_id or request.name or request.host,
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
            request.remote_workspace_id or request.name or request.host,
            exc_info=True,
        )
        return RemoteWorkspaceConnectionTestResponse(
            remote_workspace_id=request.remote_workspace_id,
            available=False,
            message="Remote Workspace connection test failed.",
        )
