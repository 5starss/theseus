from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from src.auth.dependencies import get_session_context
from src.auth.schemas import SessionContext
import asyncio
import json

router = APIRouter()

async def mock_event_generator(session: SessionContext):
    """
    SSE 스트림 테스트를 위한 모킹 제너레이터
    """
    yield f"event: connected\ndata: {json.dumps({'message': 'Connected to Theseus Core', 'user_id': session.user_id})}\n\n"
    await asyncio.sleep(1)
    
    yield f"event: session_initialized\ndata: {json.dumps({'project_id': session.project_id, 'permission': session.permission_level})}\n\n"
    await asyncio.sleep(1)
    
    for i in range(5):
        yield f"event: progress\ndata: {json.dumps({'step': i+1, 'status': 'processing stub logic...'})}\n\n"
        await asyncio.sleep(1)
        
    yield "event: complete\ndata: {\"message\": \"Stream stub completed successfully\"}\n\n"

@router.get("/stream")
async def stream_endpoint(session: SessionContext = Depends(get_session_context)):
    """
    인증된 사용자에게 SSE 스트림을 반환합니다.
    """
    return StreamingResponse(
        mock_event_generator(session),
        media_type="text/event-stream"
    )
