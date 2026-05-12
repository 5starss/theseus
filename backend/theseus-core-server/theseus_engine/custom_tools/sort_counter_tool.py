import json
from typing import Any, Dict, List
from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult
from pydantic import BaseModel, Field

class SortCounterToolInput(BaseModel):
    """
    정렬 횟수를 계산하기 위한 입력 모델.
    """
    numbers: List[int] = Field(..., description="정렬할 숫자 리스트 (4 이하의 숫자)")

class SortCounterTool(BaseTool):
    """
    사용자가 제공한 숫자 리스트를 정렬하고, 정렬 과정에서의 비교 횟수를 반환하는 도구입니다.
    (Bubble Sort 알고리즘 기준)
    """
    name = "sort_counter_tool"
    description = "숫자 리스트를 정렬하고 정렬 과정에서 발생한 비교 횟수를 반환합니다. 입력 리스트의 숫자는 4 이하여야 합니다."
    input_model = SortCounterToolInput
    permission_level = 1

    example_queries = [
        " [1, 3, 2, 4] 정렬 횟수 알려줘",
        "숫자 [4, 1, 2, 3] 정렬하면 몇 번 비교해?",
        "정렬 횟수 계산해줘: [2, 1, 4, 3]"
    ]

    async def execute(self, arguments: SortCounterToolInput, context: ToolExecutionContext) -> ToolResult:
        try:
            nums = arguments.numbers

            # 제약 조건 확인: 숫자 4 이하인지 확인
            if any(n > 4 for n in nums):
                return ToolResult(
                    output=json.dumps({"error": "모든 숫자는 4 이하여야 합니다."}, ensure_ascii=False),
                    is_error=True
                )

            # Bubble Sort 구현 및 비교 횟수 카운트
            n = len(nums)
            arr = list(nums)  # 원본 보존을 위해 복사
            comparison_count = 0

            for i in range(n):
                for j in range(0, n - i - 1):
                    comparison_count += 1
                    if arr[j] > arr[j + 1]:
                        arr[j], arr[j + 1] = arr[j + 1], arr[j]

            result_data: Dict[str, Any] = {
                "input": nums,
                "sorted_list": arr,
                "comparison_count": comparison_count
            }

            return ToolResult(output=json.dumps(result_data, ensure_ascii=False, indent=2))

        except Exception as e:
            return ToolResult(output=f"정렬 횟수를 계산하는 중 오류가 발생했습니다: {str(e)}", is_error=True)
