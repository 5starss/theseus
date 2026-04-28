from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult
from pydantic import BaseModel, Field

# --- Tool 1: Dummy Echo (권한 레벨 1) ---
class DummyInput(BaseModel):
    message: str = Field(description="에코 출력할 메시지")

class DummyTool(BaseTool):
    name = "dummy_echo"
    description = "단순히 입력받은 메시지를 그대로 반환하는 테스트 도구입니다."
    input_model = DummyInput
    
    async def execute(self, arguments: DummyInput, context: ToolExecutionContext) -> ToolResult:
        return ToolResult(output=f"[Echo] {arguments.message}")

# --- Tool 2: System Reboot (권한 레벨 3) ---
class SystemRebootInput(BaseModel):
    force: bool = Field(default=False, description="강제 재부팅 여부")

class SystemRebootTool(BaseTool):
    name = "system_reboot"
    description = "시스템을 재부팅하는 강력한 도구입니다. 관리자 권한이 필요합니다."
    input_model = SystemRebootInput
    
    async def execute(self, arguments: SystemRebootInput, context: ToolExecutionContext) -> ToolResult:
        return ToolResult(output=f"🚨 시스템 재부팅 완료 (Force: {arguments.force})")
