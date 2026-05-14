import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from src.auth.dependencies import get_sse_session_context
from src.auth.permissions import get_project_tool_permissions
from src.auth.schemas import SessionContext, UsageMetrics
from src.builder.engine import (
    EngineBuildContext,
    EngineInitializationError,
    get_query_engine,
)
from src.db.postgres import get_db
from src.db.repositories.billing import BillingOutboxRepository
from src.history.service import (
    load_history_messages,
    persist_assistant_message,
    persist_user_message,
)
from src.plan.service import restore_plan_after_stream, validate_executing_plan_binding
from theseus_engine.models.state import AgentMode

router = APIRouter()
logger = logging.getLogger(__name__)


class CoreStreamRequest(BaseModel):
    """Server-to-server stream request body from API Server."""

    model_config = ConfigDict(populate_by_name=True)

    prompt: str
    chat_session_id: int = Field(alias="chatSessionId")
    project_id: int | None = Field(default=None, alias="projectId")
    mode: str = "AGENT"
    plan_id: str | None = Field(default=None, alias="planId")
    remote_workspace_id: int | None = Field(default=None, alias="remoteWorkspaceId")


def sse_event(event_type: str, data: dict) -> str:
    """
    SSE 포맷에 맞춰 이벤트를 생성합니다.
    """
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _truncate_tool_output(output: object, max_length: int = 500) -> str:
    text = str(output)
    if len(text) <= max_length:
        return text
    return text[:max_length] + "..."


def _resolve_stream_mode(raw_mode: str, *, plan_id: str | None) -> AgentMode:
    if plan_id:
        return AgentMode.PLAN

    normalized = (raw_mode or "AGENT").strip().upper()
    mode_map = {
        "ASK": AgentMode.ASK,
        "AGENT": AgentMode.AGENT,
        "PLAN": AgentMode.PLAN,
    }
    if normalized not in mode_map:
        raise HTTPException(
            status_code=422,
            detail="mode must be one of ASK, AGENT, or PLAN",
        )
    return mode_map[normalized]


async def stream_agent_response(
    session: SessionContext,
    chat_session_id: int,
    prompt: str,
    engine_context: EngineBuildContext,
    db: Session,
):
    """Request-agnostic SSE handler for a single Theseus engine run."""
    usage_data = UsageMetrics(model_name="unknown", prompt_tokens=0, completion_tokens=0, total_tokens=0)
    assistant_chunks: list[str] = []

    yield sse_event(
        "connected",
        {
            "message": "Theseus Core Stream Connected",
            "user_id": session.user_id,
            "project_id": session.project_id,
            "chat_session_id": chat_session_id,
        },
    )

    try:
        assembly = get_query_engine(engine_context)
        usage_data.model_name = assembly.model_name

        logger.info(
            "Starting Theseus stream for user=%s project=%s mode=%s tools=%s",
            session.user_id,
            session.project_id,
            engine_context.mode.name,
            ",".join(assembly.allowed_tools),
        )

        async for event in assembly.engine.submit_message(prompt):
            if isinstance(event, assembly.assistant_text_delta_type):
                assistant_chunks.append(event.text)
                yield sse_event("chunk", {"content": event.text})
            elif isinstance(event, assembly.tool_execution_started_type):
                logger.info(
                    "Theseus tool started: user=%s project=%s chat_session=%s mode=%s tool=%s input_keys=%s",
                    session.user_id,
                    session.project_id,
                    chat_session_id,
                    engine_context.mode.name,
                    event.tool_name,
                    sorted((event.tool_input or {}).keys()),
                )
                yield sse_event(
                    "status",
                    {"message": f"Executing tool: {event.tool_name}"},
                )
            elif isinstance(event, assembly.tool_execution_completed_type):
                logger.info(
                    "Theseus tool completed: user=%s project=%s chat_session=%s mode=%s tool=%s is_error=%s output_len=%s",
                    session.user_id,
                    session.project_id,
                    chat_session_id,
                    engine_context.mode.name,
                    event.tool_name,
                    event.is_error,
                    len(str(event.output or "")),
                )
                yield sse_event(
                    "tool_result",
                    {
                        "tool_name": event.tool_name,
                        "output": _truncate_tool_output(event.output),
                    },
                )
            elif isinstance(event, assembly.error_event_type):
                logger.warning(
                    "Theseus stream error event: user=%s project=%s chat_session=%s mode=%s message=%s",
                    session.user_id,
                    session.project_id,
                    chat_session_id,
                    engine_context.mode.name,
                    event.message,
                )
                yield sse_event("error", {"message": event.message})
            elif event.__class__.__name__ == "AgentLoopStatus":
                phase = getattr(event, "phase", None)
                logger.info(
                    "Theseus agent loop status: user=%s project=%s chat_session=%s mode=%s phase=%s turn=%s tool=%s tool_count=%s is_error=%s message=%s",
                    session.user_id,
                    session.project_id,
                    chat_session_id,
                    engine_context.mode.name,
                    phase,
                    getattr(event, "turn", None),
                    getattr(event, "tool_name", None),
                    getattr(event, "tool_count", None),
                    getattr(event, "is_error", None),
                    getattr(event, "message", None),
                )
            else:
                logger.debug(
                    "Theseus stream event ignored by route: type=%s",
                    event.__class__.__name__,
                )

        total_usage = getattr(assembly.engine, "total_usage", None)
        if total_usage:
            usage_data.prompt_tokens = getattr(total_usage, "prompt_tokens", 0)
            usage_data.completion_tokens = getattr(total_usage, "completion_tokens", 0)
            usage_data.total_tokens = getattr(total_usage, "total_tokens", 0)

        is_assistant_message_saved = await persist_assistant_message(
            session=session,
            chat_session_id=chat_session_id,
            content="".join(assistant_chunks),
        )
        if not is_assistant_message_saved:
            yield sse_event("error", {"message": "Assistant message persistence failed"})
            return

        yield sse_event(
            "completed",
            {
                "status": "done",
                "total_tokens": usage_data.total_tokens,
                "model_name": usage_data.model_name,
            },
        )
    except EngineInitializationError as exc:
        logger.warning("Theseus engine initialization failed: %s", exc)
        yield sse_event("error", {"message": str(exc)})
    except Exception as exc:
        logger.error("Theseus stream error: %s", exc, exc_info=True)
        yield sse_event("error", {"message": str(exc)})
    finally:
        if engine_context.plan_id:
            try:
                restore_plan_after_stream(
                    db,
                    plan_id=engine_context.plan_id,
                    project_id=str(session.project_id),
                    chat_session_id=chat_session_id,
                    executing_user_id=str(session.user_id),
                )
            except Exception as exc:
                logger.error("Plan restoration failed: %s", exc, exc_info=True)
        outbox_record = BillingOutboxRepository(db).enqueue(
            user_id=session.user_id,
            project_id=session.project_id,
            usage=usage_data,
        )
        logger.info(
            "Billing outbox enqueued for user %s with record %s",
            session.user_id,
            outbox_record.id,
        )


async def create_streaming_response(
    *,
    prompt: str,
    chat_session_id: int,
    mode: str,
    plan_id: str | None,
    remote_workspace_id: int | None,
    session: SessionContext,
    db: Session,
) -> StreamingResponse:
    """Assemble stream context and return a Core SSE response."""

    if not prompt.strip():
        raise HTTPException(status_code=422, detail="Prompt must not be blank")

    project_tool_permissions = await get_project_tool_permissions(
        project_id=session.project_id,
        user_id=session.user_id,
    )

    history_messages = await load_history_messages(session, chat_session_id)
    bound_plan = None
    stream_mode = _resolve_stream_mode(mode, plan_id=plan_id)
    logger.info(
        "Fetched project tool permissions: user=%s project=%s chat_session=%s mode=%s tool_count=%d tools=%s",
        session.user_id,
        session.project_id,
        chat_session_id,
        stream_mode.name,
        len(project_tool_permissions),
        ",".join(sorted(project_tool_permissions.keys())),
    )
    if plan_id:
        bound_plan = validate_executing_plan_binding(
            db,
            plan_id=plan_id,
            project_id=str(session.project_id),
            chat_session_id=chat_session_id,
        )

    engine_context = EngineBuildContext(
        user_level=session.permission_level,
        project_tool_permissions=project_tool_permissions,
        mode=stream_mode,
        approval_policy="reject",
        user_query=prompt,
        history_messages=history_messages,
        session_id=str(chat_session_id),
        project_id=str(session.project_id),
        actor_user_id=str(session.user_id),
        chat_session_id=chat_session_id,
        plan_id=plan_id,
        plan_content=bound_plan.content if bound_plan is not None else None,
        remote_workspace_id=remote_workspace_id,
    )

    await persist_user_message(session, chat_session_id, prompt)

    return StreamingResponse(
        stream_agent_response(session, chat_session_id, prompt, engine_context, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/stream")
async def stream_endpoint(
    prompt: str = Query(..., min_length=1),
    chat_session_id: int = Query(..., ge=1),
    mode: str = Query("AGENT"),
    plan_id: str | None = Query(None),
    remote_workspace_id: int | None = Query(None),
    remote_workspace_id_camel: int | None = Query(None, alias="remoteWorkspaceId"),
    session: SessionContext = Depends(get_sse_session_context),
    db: Session = Depends(get_db),
):
    """
    인증된 사용자에게 SSE 스트림을 반환하며, 종료 시 과금을 수행합니다.
    """
    if not prompt.strip():
        raise HTTPException(status_code=422, detail="Prompt must not be blank")

    project_tool_permissions = await get_project_tool_permissions(
        project_id=session.project_id,
        user_id=session.user_id,
    )

    history_messages = await load_history_messages(session, chat_session_id)
    bound_plan = None
    stream_mode = _resolve_stream_mode(mode, plan_id=plan_id)
    logger.info(
        "Fetched project tool permissions: user=%s project=%s chat_session=%s mode=%s tool_count=%d tools=%s",
        session.user_id,
        session.project_id,
        chat_session_id,
        stream_mode.name,
        len(project_tool_permissions),
        ",".join(sorted(project_tool_permissions.keys())),
    )
    if plan_id:
        bound_plan = validate_executing_plan_binding(
            db,
            plan_id=plan_id,
            project_id=str(session.project_id),
            chat_session_id=chat_session_id,
        )

    resolved_remote_workspace_id = (
        remote_workspace_id
        if remote_workspace_id is not None
        else remote_workspace_id_camel
    )

    engine_context = EngineBuildContext(
        user_level=session.permission_level,
        project_tool_permissions=project_tool_permissions,
        mode=stream_mode,
        approval_policy="reject",
        user_query=prompt,
        history_messages=history_messages,
        session_id=str(chat_session_id),
        project_id=str(session.project_id),
        actor_user_id=str(session.user_id),
        chat_session_id=chat_session_id,
        plan_id=plan_id,
        plan_content=bound_plan.content if bound_plan is not None else None,
        remote_workspace_id=resolved_remote_workspace_id,
    )

    await persist_user_message(session, chat_session_id, prompt)

    return StreamingResponse(
        stream_agent_response(session, chat_session_id, prompt, engine_context, db),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 스트리밍 최적화
        },
    )


@router.post("/stream")
async def stream_endpoint_post(
    request: CoreStreamRequest,
    session: SessionContext = Depends(get_sse_session_context),
    db: Session = Depends(get_db),
):
    """Stream chat using a JSON body so sensitive Remote Workspace fields stay out of URLs."""

    return await create_streaming_response(
        prompt=request.prompt,
        chat_session_id=request.chat_session_id,
        mode=request.mode,
        plan_id=request.plan_id,
        remote_workspace_id=request.remote_workspace_id,
        session=session,
        db=db,
    )
