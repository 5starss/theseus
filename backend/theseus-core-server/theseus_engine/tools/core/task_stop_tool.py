"""Background task stop tool."""

from __future__ import annotations

import logging
from pydantic import BaseModel, Field
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult

from theseus_engine.tasks.manager import get_task_manager

log = logging.getLogger(__name__)


class TaskStopInput(BaseModel):
    """Arguments for stopping a task."""

    task_id: str = Field(description="Task identifier to stop")


class TaskStopTool(BaseTool):
    """Stop a running background task."""

    name = "task_stop"
    description = "Stop a running background task by its ID."
    input_model = TaskStopInput
    permission_level = 2

    async def execute(
        self, arguments: TaskStopInput, context: ToolExecutionContext
    ) -> ToolResult:
        try:
            task = await get_task_manager().stop_task(arguments.task_id)
            return ToolResult(
                output=f"✅ Task stopped: {task.id} ({task.description})"
            )
        except ValueError as exc:
            return ToolResult(output=str(exc), is_error=True)
