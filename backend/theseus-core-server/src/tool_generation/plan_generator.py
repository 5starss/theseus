from src.tool_generation.schemas import PlanAiRequest, ToolPlanResult


class ToolPlanGenerationNotImplementedError(RuntimeError):
    pass


class ToolPlanGenerator:
    async def generate(self, request: PlanAiRequest) -> ToolPlanResult:
        raise ToolPlanGenerationNotImplementedError(
            f"Tool PLAN generation is not connected yet. requestType={request.request_type}"
        )
