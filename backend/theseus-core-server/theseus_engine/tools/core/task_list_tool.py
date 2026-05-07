"""Background task listing tool."""

from __future__ import annotations

import logging
from pydantic import BaseModel, Field
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult

from theseus_engine.tasks.manager import get_task_manager

log = logging.getLogger(__name__)


class TaskListInput(BaseModel):
    """Arguments for task listing."""

    status: str | None = Field(
        default=None,
        description="Optional status filter: running, completed, failed, stopped",
    )


class TaskListTool(BaseTool):
    """List all background tasks and their statuses."""

    name = "task_list"
    description = "List all background tasks with their IDs and statuses."
    input_model = TaskListInput
    permission_level = 1

    async def execute(
        self, arguments: TaskListInput, context: ToolExecutionContext
    ) -> ToolResult:
        tasks = get_task_manager().list_tasks(status=arguments.status)
        if not tasks:
            return ToolResult(output="(No running tasks)")
        lines = [
            f"{t.id}  [{t.status:>9}]  {t.type}  {t.description}"
            for t in tasks
        ]
        return ToolResult(output="\n".join(lines))
