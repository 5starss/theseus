"""Background task output reader tool."""

from __future__ import annotations

import logging
from pydantic import BaseModel, Field
from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult

from theseus_engine.tasks.manager import get_task_manager

log = logging.getLogger(__name__)


class TaskOutputInput(BaseModel):
    """Arguments for task output retrieval."""

    task_id: str = Field(description="Task identifier (returned by task_create)")
    max_bytes: int = Field(
        default=12000, ge=1, le=100000,
        description="Maximum bytes of output to return",
    )


class TaskOutputTool(BaseTool):
    """Read stdout/stderr output of a background task."""

    name = "task_output"
    description = "Read the output log of a running or completed background task."
    input_model = TaskOutputInput
    permission_level = 1

    async def execute(
        self, arguments: TaskOutputInput, context: ToolExecutionContext
    ) -> ToolResult:
        try:
            output = get_task_manager().read_task_output(
                arguments.task_id,
                max_bytes=arguments.max_bytes,
                cwd=context.cwd,
            )
            return ToolResult(output=output)
        except ValueError as exc:
            return ToolResult(output=str(exc), is_error=True)
