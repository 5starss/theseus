import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
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
            "Starting Theseus stream for user=%s project=%s tools=%s",
            session.user_id,
            session.project_id,
            ",".join(assembly.allowed_tools),
        )

        async for event in assembly.engine.submit_message(prompt):
            if isinstance(event, assembly.assistant_text_delta_type):
                assistant_chunks.append(event.text)
                yield sse_event("chunk", {"content": event.text})
            elif isinstance(event, assembly.tool_execution_started_type):
                yield sse_event(
                    "status",
                    {"message": f"Executing tool: {event.tool_name}"},
                )
            elif isinstance(event, assembly.tool_execution_completed_type):
                yield sse_event(
                    "tool_result",
                    {
                        "tool_name": event.tool_name,
                        "output": _truncate_tool_output(event.output),
                    },
                )
            elif isinstance(event, assembly.error_event_type):
                yield sse_event("error", {"message": event.message})

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
                    project_id=session.project_id,
                    chat_session_id=chat_session_id,
                    executing_user_id=session.user_id,
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


@router.get("/stream")
async def stream_endpoint(
    prompt: str = Query(..., min_length=1),
    chat_session_id: int = Query(..., ge=1),
    plan_id: str | None = Query(None),
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
    mode = AgentMode.AGENT
    if plan_id:
        bound_plan = validate_executing_plan_binding(
            db,
            plan_id=plan_id,
            project_id=session.project_id,
            chat_session_id=chat_session_id,
        )
        mode = AgentMode.PLAN

    engine_context = EngineBuildContext(
        user_level=session.permission_level,
        project_tool_permissions=project_tool_permissions,
        mode=mode,
        approval_policy="reject",
        history_messages=history_messages,
        session_id=str(chat_session_id),
        plan_id=plan_id,
        plan_content=bound_plan.content if bound_plan is not None else None,
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
