import json
from datetime import datetime
from typing import Any, Dict
from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult
from pydantic import BaseModel, Field

class SystemTimeToolInput(BaseModel):
    """
    시스템 시간을 조회하기 위한 입력 모델.
    현재는 별도의 입력 파라미터가 필요하지 않습니다.
    """
    pass

class SystemTimeTool(BaseTool):
    """
    현재 시스템의 날짜와 시간을 조회하는 도구입니다.
    """
    name = "system_time_tool"
    description = "현재 시스템의 날짜와 시간을 조회하여 반환합니다."
    input_model = SystemTimeToolInput
    permission_level = 1

    example_queries = [
        "현재 시간 알려줘",
        "지금 몇 시야?",
        "오늘 날짜가 뭐야?",
        "What is the current time?",
        "Show current date and time"
    ]

    async def execute(self, arguments: SystemTimeToolInput, context: ToolExecutionContext) -> ToolResult:
        try:
            now = datetime.now()
            result_data: Dict[str, Any] = {
                "iso_format": now.isoformat(),
                "readable_format": now.strftime("%Y-%m-%d %H:%M:%S"),
                "year": now.year,
                "month": now.month,
                "day": now.day,
                "hour": now.hour,
                "minute": now.minute,
                "second": now.second,
                "timezone": "local"
            }

            return ToolResult(output=json.dumps(result_data, ensure_ascii=False, indent=2))

        except Exception as e:
            return ToolResult(output=f"시스템 시간을 조회하는 중 오류가 발생했습니다: {str(e)}", is_error=True)
