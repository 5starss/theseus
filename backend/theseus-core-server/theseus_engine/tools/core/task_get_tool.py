"""Background task detail / status tool."""

from __future__ import annotations

import logging
from pydantic import BaseModel, Field
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult

from theseus_engine.tasks.manager import get_task_manager

log = logging.getLogger(__name__)


class TaskGetInput(BaseModel):
    """Arguments for task lookup."""

    task_id: str = Field(description="Task identifier")


class TaskGetTool(BaseTool):
    """Return detailed information about a background task."""

    name = "task_get"
    description = "Get detailed status and metadata for a specific background task."
    input_model = TaskGetInput
    permission_level = 1

    async def execute(
        self, arguments: TaskGetInput, context: ToolExecutionContext
    ) -> ToolResult:
        task = get_task_manager().get_task(arguments.task_id)
        if task is None:
            return ToolResult(
                output=f"태스크를 찾을 수 없습니다: {arguments.task_id}",
                is_error=True,
            )
        return ToolResult(output=str(task))
