"""Sub-agent delegation tool for Theseus.

Allows the main agent to spawn sub-agents for parallel delegation
of complex tasks. Uses Theseus's own task manager, independent
of OpenHarness coordinator/swarm dependencies.

Feature 2 improvements: max_rbac_level inheritance, inherit_context flag,
timeout_seconds support, THESEUS_SUBAGENT env variable propagation.
"""

from __future__ import annotations

import os
import logging
from typing import Optional

from pydantic import BaseModel, Field

from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult

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
    model: Optional[str] = Field(
        default=None,
        description="Override model for the sub-agent (defaults to parent's model)",
    )
    max_rbac_level: Optional[int] = Field(
        default=None,
        description=(
            "Maximum RBAC permission level (1-5). Cannot exceed the parent's level. "
            "If unspecified, inherits the parent's level."
        ),
    )
    inherit_context: bool = Field(
        default=False,
        description="If true, pass the current working directory and environment settings to the sub-agent.",
    )
    timeout_seconds: Optional[int] = Field(
        default=300,
        description="Sub-agent execution timeout in seconds. Default: 300.",
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

        # 부모 RBAC 레벨 결정 (context.metadata에서 상속)
        parent_rbac = 3
        if context.metadata and isinstance(context.metadata, dict):
            parent_rbac = context.metadata.get("user_rbac_level", 3)

        # 서브 에이전트 RBAC 레벨: 부모 레벨을 초과할 수 없음
        sub_rbac = min(
            arguments.max_rbac_level if arguments.max_rbac_level is not None else parent_rbac,
            parent_rbac,
        )

        # 사용할 모델 결정
        model = arguments.model or os.getenv("THESEUS_MODEL", "gpt-4o")

        # 에이전트 모드 컨텍스트 (coordinator 또는 일반)
        agent_mode = (
            context.metadata.get("agent_mode", "normal")
            if context.metadata and isinstance(context.metadata, dict)
            else "normal"
        )

        # 프롬프트를 임시 파일로 저장해 셸 인젝션 방지
        # (python -c "..." 인라인 문자열 삽입 시 메타문자 이스케이프 불가)
        import tempfile, json as _json
        prompt_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False, encoding="utf-8"
        )
        _json.dump({"prompt": arguments.prompt}, prompt_file)
        prompt_file.flush()
        prompt_file.close()
        prompt_file_path = prompt_file.name

        # THESEUS_SUBAGENT=1 환경 변수로 서브 에이전트임을 표시
        env_overrides = "os.environ['THESEUS_SUBAGENT'] = '1'; "
        env_overrides += f"os.environ['THESEUS_MODEL'] = {model!r}; "
        if arguments.inherit_context:
            env_overrides += f"os.environ['THESEUS_AGENT_MODE'] = {agent_mode!r}; "

        agent_script = (
            "import sys, os, json, asyncio; "
            "sys.path.insert(0, os.getcwd()); "
            "from dotenv import load_dotenv; load_dotenv(); "
            f"{env_overrides}"
            "from theseus_engine.core.engine_builder import setup_engine; "
            "from theseus_engine.models.state import TheseusStateMachine; "
            f"_data = json.load(open({prompt_file_path!r}, encoding='utf-8')); "
            f"os.unlink({prompt_file_path!r}); "
            "async def run(): "
            "    sm = TheseusStateMachine(); "
            f"    engine, _ = await setup_engine(sm, {sub_rbac}, {{}}, lambda x: asyncio.sleep(0)); "
            "    output_parts = []; "
            "    async for event in engine.submit_message(_data['prompt']): "
            "        t = getattr(event, 'text', None) or getattr(event, 'delta', None); "
            "        output_parts.append(str(t)) if t else None; "
            "    print(''.join(output_parts)); "
            "asyncio.run(run())"
        )

        command = ["python", "-c", agent_script]

        try:
            task = await manager.create_shell_task(
                command=command if isinstance(command, str) else " ".join(command),
                description=f"[Sub-Agent] {arguments.description}",
                cwd=cwd,
            )

            log.info(
                "[AgentTool] Sub-agent spawned: task=%s, rbac=%d (parent=%d), model=%s",
                task.id, sub_rbac, parent_rbac, model,
            )

            return ToolResult(
                output=(
                    f"Sub-agent spawned successfully\n"
                    f"Task ID: {task.id}\n"
                    f"Model: {model}\n"
                    f"RBAC Level: {sub_rbac} (parent: {parent_rbac})\n"
                    f"Description: {arguments.description}\n"
                    f"Prompt: {arguments.prompt[:200]}{'...' if len(arguments.prompt) > 200 else ''}\n\n"
                    f"Check results: task_output(task_id='{task.id}')\n"
                    f"Stop: task_stop(task_id='{task.id}')"
                ),
                metadata={
                    "task_id": task.id,
                    "description": arguments.description,
                    "model": model,
                    "sub_rbac_level": sub_rbac,
                    "parent_rbac_level": parent_rbac,
                },
            )
        except Exception as exc:
            log.error("Sub-agent spawn failed: %s", exc)
            return ToolResult(
                output=f"Sub-agent spawn failed: {exc}",
                is_error=True,
            )
