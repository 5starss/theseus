"""Sub-agent delegation tool for Theseus.

메인 에이전트가 하위 에이전트를 스폰하여 복잡한 작업을
병렬로 위임할 수 있게 합니다. Theseus의 자체 태스크 매니저를 사용하여
OpenHarness의 coordinator/swarm 의존성 없이 독립적으로 동작합니다.
"""

from __future__ import annotations

import os
import json
import logging

from pydantic import BaseModel, Field

from openharness.tools.base import BaseTool, ToolExecutionContext, ToolResult

from theseus_engine.tasks.manager import get_task_manager

log = logging.getLogger(__name__)


class AgentInput(BaseModel):
    """Arguments for spawning a sub-agent."""

    description: str = Field(
        description="Short description of the delegated task"
    )
    prompt: str = Field(
        description=(
            "Full, detailed prompt for the sub-agent. "
            "Be specific — the sub-agent has no context from the current conversation."
        )
    )
    model: str | None = Field(
        default=None,
        description="Override model for the sub-agent (defaults to parent's model)",
    )


class AgentTool(BaseTool):
    """Spawn a sub-agent to handle a delegated task in the background.

    The sub-agent runs as a separate process using theseus_cli.py,
    inheriting the current workspace but with its own independent
    conversation context. Results can be polled via task_output.
    """

    name = "agent"
    description = (
        "Delegate work to a background sub-agent. The sub-agent gets its own "
        "conversation and tools. Use this for parallelizable tasks like "
        "'write tests for module X', 'refactor component Y', etc. "
        "Returns a task_id — use task_output to check results."
    )
    input_model = AgentInput
    permission_level = 3

    async def execute(
        self, arguments: AgentInput, context: ToolExecutionContext
    ) -> ToolResult:
        manager = get_task_manager()
        cwd = str(context.cwd)

        # 사용할 모델 결정
        model = (
            arguments.model
            or os.getenv("OPENHARNESS_MODEL", "gpt-4o")
        )

        # 서브 에이전트에게 전달할 프롬프트를 환경 변수로 인코딩
        # theseus_cli.py --auto 모드로 단일 프롬프트 실행
        escaped_prompt = arguments.prompt.replace('"', '\\"')

        # 서브 에이전트를 별도 프로세스로 실행
        # Python의 -c 옵션을 사용하여 theseus_cli의 자동 모드를 호출
        agent_script = (
            "import sys, os; "
            "sys.path.insert(0, os.getcwd()); "
            "from dotenv import load_dotenv; load_dotenv(); "
            "import asyncio; "
            "from theseus_engine.core.engine_builder import setup_engine; "
            "from theseus_engine.models.state import TheseusStateMachine; "
            "async def run(): "
            "    sm = TheseusStateMachine(); "
            f"    engine, _ = setup_engine(sm, 3, {{}}, lambda x: asyncio.sleep(0)); "
            f"    result = await engine.query('''{escaped_prompt}'''); "
            "    print(result.text if hasattr(result, 'text') else str(result)); "
            "asyncio.run(run())"
        )

        command = f'python -c "{agent_script}"'

        try:
            task = await manager.create_shell_task(
                command=command,
                description=f"[Sub-Agent] {arguments.description}",
                cwd=cwd,
            )

            return ToolResult(
                output=(
                    f"✅ 서브 에이전트 스폰 완료\n"
                    f"Task ID: {task.id}\n"
                    f"Model: {model}\n"
                    f"Description: {arguments.description}\n"
                    f"Prompt: {arguments.prompt[:200]}{'...' if len(arguments.prompt) > 200 else ''}\n\n"
                    f"📋 결과 확인: task_output(task_id='{task.id}')\n"
                    f"🛑 중지: task_stop(task_id='{task.id}')"
                ),
                metadata={
                    "task_id": task.id,
                    "description": arguments.description,
                    "model": model,
                },
            )
        except Exception as exc:
            log.error("Sub-agent spawn failed: %s", exc)
            return ToolResult(
                output=f"서브 에이전트 스폰 실패: {exc}",
                is_error=True,
            )
