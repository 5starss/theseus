from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Optional, Dict, Any

class SandboxInput(BaseModel):
    project_id: str
    tool_name: str
    tool_code: str
    payload: Dict[str, Any]
    timeout_seconds: int = 10

class SandboxOutput(BaseModel):
    success: bool
    result: Optional[Dict[str, Any]] = None
    stdout: str = ""
    stderr: str = ""
    error_message: Optional[str] = None
    execution_time_ms: int = 0

class ToolRunner(ABC):
    @abstractmethod
    async def execute(self, request: SandboxInput) -> SandboxOutput:
        """
        주어진 툴 코드를 격리된 환경에서 실행하고 결과를 반환합니다.
        """
        pass
