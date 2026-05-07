from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult
from pydantic import BaseModel, Field
import datetime

class GetCurrentTimeToolInput(BaseModel):
    pass

class GetCurrentTimeTool(BaseTool):
    name = "get_current_time"
    description = "현재 시스템의 날짜와 시간을 ISO 8601 형식으로 반환합니다."
    input_model = GetCurrentTimeToolInput
    permission_level = 1

    async def execute(self, arguments: GetCurrentTimeToolInput, context: ToolExecutionContext) -> ToolResult:
        try:
            # 로컬 타임존을 포함한 현재 시간 가져오기
            now = datetime.datetime.now().astimezone()
            return ToolResult(output=now.isoformat())
        except Exception as e:
            return ToolResult(output=f"Error retrieving current time: {str(e)}", is_error=True)

    @classmethod
    def example_queries(cls):
        return [
            "현재 시간 알려줘",
            "지금 몇 시야?",
            "what is the current time"
        ]
