"""Background task creation tool."""

from __future__ import annotations

import logging
from pydantic import BaseModel, Field
from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult

from theseus_engine.tasks.manager import get_task_manager

log = logging.getLogger(__name__)


class TaskCreateInput(BaseModel):
    """Arguments for task creation."""

    command: str = Field(description="Shell command to run in the background")
    description: str = Field(description="Short description of the task")


class TaskCreateTool(BaseTool):
    """Create a background shell task that runs asynchronously."""

    name = "task_create"
    description = (
        "Start a shell command in the background (e.g. dev servers, builds). "
        "Returns a task ID that you can use with task_output, task_get, task_stop."
    )
    input_model = TaskCreateInput
    permission_level = 3

    async def execute(
        self, arguments: TaskCreateInput, context: ToolExecutionContext
    ) -> ToolResult:
        try:
            task = await get_task_manager().create_shell_task(
                command=arguments.command,
                description=arguments.description,
                cwd=context.cwd,
            )
            return ToolResult(
                output=(
                    f"✅ 백그라운드 태스크 생성 완료\n"
                    f"ID: {task.id}\n"
                    f"Command: {arguments.command}\n"
                    f"Description: {arguments.description}\n"
                    f"task_output 도구로 출력을 확인하세요."
                )
            )
        except Exception as exc:
            return ToolResult(
                output=f"태스크 생성 실패: {exc}", is_error=True
            )
