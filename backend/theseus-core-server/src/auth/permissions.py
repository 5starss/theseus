from fastapi import HTTPException, status

from src.auth.client import (
    PermissionAccessDeniedError,
    PermissionBackendUnavailableError,
    PermissionClient,
    PermissionInvalidResponseError,
)
from src.config import settings

MOCK_PROJECT_TOOL_PERMISSIONS: dict[str, int] = {
    "bash": 3,
    "read_file": 1,
    "write_file": 2,
    "edit_file": 2,
    "local_write_report": 2,
    "glob": 1,
    "grep": 1,
    "web_search": 1,
    "web_fetch": 1,
    "dummy_echo": 1,
    "create_tool": 2,
    "system_reboot": 5,
}

PROJECT_ACCESS_DENIED = "Project access denied"
PERMISSION_SERVICE_INVALID_DATA = "Permission service returned invalid data"
PERMISSION_SERVICE_UNAVAILABLE = "Permission service unavailable"

permission_client = PermissionClient()


async def get_project_tool_permissions(
    project_id: str,
    user_id: str,
    session_id: str | None = None,
) -> dict[str, int]:
    del session_id  # Reserved for a future session-aware permission contract.

    if settings.mock_auth_enabled:
        return dict(MOCK_PROJECT_TOOL_PERMISSIONS)

    try:
        return await permission_client.fetch_project_tool_permissions(
            project_id=str(project_id),
            user_id=str(user_id),
        )
    except PermissionAccessDeniedError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=PROJECT_ACCESS_DENIED,
        ) from exc
    except PermissionInvalidResponseError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=PERMISSION_SERVICE_INVALID_DATA,
        ) from exc
    except PermissionBackendUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=PERMISSION_SERVICE_UNAVAILABLE,
        ) from exc
