"""Optional server adapter for create_tool.

The standalone engine can be imported without ``src``.  When the runtime is
assembled by the FastAPI server, this adapter delegates to ``src.tooling`` and
keeps that dependency out of the core ToolCreatorTool implementation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ServerCreateToolContext:
    project_id: str
    creator_user_id: str
    chat_session_id: int
    plan_id: str
    run_id: str | None = None


def resolve_server_create_tool_context(
    metadata: dict[str, Any],
    *,
    run_id: str | None = None,
) -> ServerCreateToolContext | None:
    project_id = metadata.get("project_id")
    user_id = metadata.get("user_id")
    chat_session_id = metadata.get("chat_session_id")
    plan_id = metadata.get("plan_id")
    if not (project_id and user_id and chat_session_id is not None and plan_id):
        return None
    return ServerCreateToolContext(
        project_id=str(project_id),
        creator_user_id=str(user_id),
        chat_session_id=int(chat_session_id),
        plan_id=str(plan_id),
        run_id=run_id,
    )


async def create_tool_via_server(
    *,
    tool_name: str,
    python_code: str,
    permission_level: int,
    server_context: ServerCreateToolContext,
    registry: Any = None,
    tool_permissions: Any = None,
) -> Any:
    try:
        from src.tooling import ServerToolCreationRequest, create_tool_for_server
    except ImportError as exc:
        raise RuntimeError("server_tooling_unavailable") from exc

    return await create_tool_for_server(
        ServerToolCreationRequest(
            tool_name=tool_name,
            python_code=python_code,
            permission_level=permission_level,
            project_id=server_context.project_id,
            creator_user_id=server_context.creator_user_id,
            chat_session_id=server_context.chat_session_id,
            plan_id=server_context.plan_id,
            run_id=server_context.run_id,
        ),
        registry=registry,
        tool_permissions=tool_permissions,
    )
