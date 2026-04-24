import json
import time
import asyncio
from typing import Dict, Any
import logging
from src.sandbox.base import ToolRunner, SandboxInput, SandboxOutput

logger = logging.getLogger(__name__)

class DockerExecutor(ToolRunner):
    """
    MVP: 실제 Docker SDK 연동 전, 동작을 모방(Mock/Stub)하거나
    향후 docker-py 라이브러리를 통해 DinD 환경에서 컨테이너를 스핀업하는 클래스입니다.
    """
    def __init__(self):
        # 향후 import docker; self.client = docker.from_env() 추가
        pass

    async def execute(self, request: SandboxInput) -> SandboxOutput:
        start_time = time.time()
        
        logger.info(f"Sandbox executing tool: {request.tool_name} for project: {request.project_id}")
        
        # TODO: 실제 Docker 컨테이너 실행 로직 (docker-py 사용)
        # 1. 임시 디렉토리에 코드와 페이로드 작성
        # 2. docker client로 컨테이너 run (network_disabled=True, mem_limit, timeout)
        # 3. 로그 및 결과 수집
        
        # 여기서는 동작 모방을 위해 asyncio.sleep 사용
        await asyncio.sleep(0.5)
        
        execution_time_ms = int((time.time() - start_time) * 1000)
        
        if request.timeout_seconds < 0.5:
             return SandboxOutput(
                success=False,
                error_message="Execution timeout",
                execution_time_ms=execution_time_ms
             )
             
        # Mock 결과 반환
        return SandboxOutput(
            success=True,
            result={"mock_key": "mock_value", "payload_received": request.payload},
            stdout="Tool executed successfully in sandbox.\n",
            execution_time_ms=execution_time_ms
        )
