from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Query
from fastapi.responses import StreamingResponse
from src.auth.dependencies import get_sse_session_context
from src.auth.schemas import SessionContext, BillingUsageReport, UsageMetrics
from src.auth.client import billing_client
from src.builder.engine import EngineInitializationError, get_query_engine
import json
import logging

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
    prompt: str,
    background_tasks: BackgroundTasks,
):
    """Request-agnostic SSE handler for a single Theseus engine run."""
    usage_data = UsageMetrics(model_name="unknown", prompt_tokens=0, completion_tokens=0, total_tokens=0)

    yield sse_event(
        "connected",
        {
            "message": "Theseus Core Stream Connected",
            "user_id": session.user_id,
            "project_id": session.project_id,
        },
    )

    try:
        assembly = get_query_engine(session)
        usage_data.model_name = assembly.model_name

        logger.info(
            "Starting Theseus stream for user=%s project=%s tools=%s",
            session.user_id,
            session.project_id,
            ",".join(assembly.allowed_tools),
        )

        async for event in assembly.engine.submit_message(prompt):
            if isinstance(event, assembly.assistant_text_delta_type):
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

        yield sse_event(
            "complete",
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
        report = BillingUsageReport(
            user_id=session.user_id,
            project_id=session.project_id,
            usage=usage_data,
        )
        background_tasks.add_task(billing_client.report_usage, report)
        logger.info("Billing report queued for user %s", session.user_id)

@router.get("/stream")
async def stream_endpoint(
    background_tasks: BackgroundTasks,
    prompt: str = Query(..., min_length=1),
    session: SessionContext = Depends(get_sse_session_context),
):
    """
    인증된 사용자에게 SSE 스트림을 반환하며, 종료 시 과금을 수행합니다.
    """
    if not prompt.strip():
        raise HTTPException(status_code=422, detail="Prompt must not be blank")

    return StreamingResponse(
        stream_agent_response(session, prompt, background_tasks),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx 스트리밍 최적화
        },
    )
