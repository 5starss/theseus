from fastapi import APIRouter, Depends, BackgroundTasks
from fastapi.responses import StreamingResponse
from src.auth.dependencies import get_sse_session_context
from src.auth.schemas import SessionContext, BillingUsageReport, UsageMetrics
from src.auth.client import billing_client
from src.sandbox.base import SandboxInput
from src.sandbox.docker_executor import DockerExecutor
import asyncio
import json
import logging

router = APIRouter()
executor = DockerExecutor()
logger = logging.getLogger(__name__)

def sse_event(event_type: str, data: dict) -> str:
    """
    SSE 포맷에 맞춰 이벤트를 생성합니다.
    """
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"

async def event_generator(session: SessionContext, background_tasks: BackgroundTasks):
    """
    실제 에이전트 실행 흐름을 시뮬레이션하고 종료 후 과금 정보를 보고하는 제너레이터
    """
    usage_data = UsageMetrics(model_name="gpt-4-turbo", prompt_tokens=100, completion_tokens=50, total_tokens=150)
    
    try:
        # 1. 연결 확인 이벤트
        yield sse_event("connected", {"message": "Theseus Core Stream Connected", "user_id": session.user_id})
        await asyncio.sleep(0.3)

        # 2. 에이전트 실행 시뮬레이션 (Chunk 전송)
        message_chunks = ["안녕", "하세요", ", ", "도와", "드릴까요", "?"]
        for chunk in message_chunks:
            yield sse_event("chunk", {"content": chunk})
            await asyncio.sleep(0.1)

        # 3. 샌드박스 툴 실행 (필요 시)
        yield sse_event("status", {"message": "Executing tools in sandbox..."})
        request = SandboxInput(
            project_id=session.project_id,
            tool_name="search_knowledge",
            tool_code="", # 실제 에이전트 로직에서는 여기에 코드가 들어감
            payload={"query": "테스트"}
        )
        result = await executor.execute(request)
        yield sse_event("tool_result", {"success": result.success, "time_ms": result.execution_time_ms})

        # 4. 완료 이벤트
        yield sse_event("complete", {"status": "done", "total_tokens": usage_data.total_tokens})

    except Exception as exc:
        logger.error(f"Stream error: {exc}")
        yield sse_event("error", {"message": str(exc)})
        raise
    finally:
        # 5. 과금 데이터 전송 (스트림이 끊겨도 실행됨)
        if usage_data:
            report = BillingUsageReport(
                user_id=session.user_id,
                project_id=session.project_id,
                usage=usage_data
            )
            background_tasks.add_task(billing_client.report_usage, report)
            logger.info(f"Billing report queued for user {session.user_id}")

@router.get("/stream")
async def stream_endpoint(
    background_tasks: BackgroundTasks,
    session: SessionContext = Depends(get_sse_session_context)
):
    """
    인증된 사용자에게 SSE 스트림을 반환하며, 종료 시 과금을 수행합니다.
    """
    return StreamingResponse(
        event_generator(session, background_tasks),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no" # Nginx 스트리밍 최적화
        }
    )
