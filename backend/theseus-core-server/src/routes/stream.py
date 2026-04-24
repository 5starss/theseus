from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from src.auth.dependencies import get_sse_session_context
from src.auth.schemas import SessionContext
from src.sandbox.base import SandboxInput
from src.sandbox.docker_executor import DockerExecutor
import asyncio
import json

router = APIRouter()
executor = DockerExecutor()

async def mock_event_generator(session: SessionContext):
    """
    SSE 스트림 테스트를 위한 모킹 제너레이터
    """
    yield f"event: connected\ndata: {json.dumps({'message': 'Connected to Theseus Core', 'user_id': session.user_id})}\n\n"
    await asyncio.sleep(0.5)
    
    yield f"event: session_initialized\ndata: {json.dumps({'project_id': session.project_id, 'permission': session.permission_level})}\n\n"
    await asyncio.sleep(0.5)
    
    yield f"event: sandbox_starting\ndata: {json.dumps({'status': 'launching isolated tool runner...'})}\n\n"
    
    # Sandbox 실행 시뮬레이션
    request = SandboxInput(
        project_id=session.project_id,
        tool_name="demo_tool",
        tool_code="print('hello world')",
        payload={"arg1": "value"}
    )
    
    result = await executor.execute(request)
    
    yield f"event: sandbox_result\ndata: {json.dumps({'success': result.success, 'stdout': result.stdout, 'time_ms': result.execution_time_ms})}\n\n"
        
    yield "event: complete\ndata: {\"message\": \"Stream completed\"}\n\n"

@router.get("/stream")
async def stream_endpoint(session: SessionContext = Depends(get_sse_session_context)):
    """
    인증된 사용자에게 SSE 스트림을 반환합니다.
    """
    return StreamingResponse(
        mock_event_generator(session),
        media_type="text/event-stream"
    )
