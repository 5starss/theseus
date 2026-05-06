from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.sandbox.base import SandboxInput, SandboxUnavailableError
from src.sandbox.docker_executor import DockerExecutor

_executor = DockerExecutor()


async def run_tool_sandbox_gate(
    *,
    project_id: str,
    tool_name: str,
    tool_code: str,
    timeout_seconds: int = 10,
) -> dict[str, Any]:
    request = SandboxInput(
        project_id=project_id,
        tool_name=tool_name,
        tool_code=tool_code,
        payload={
            "tool_name": tool_name,
            "module_name": f"{project_id}:{tool_name}",
        },
        timeout_seconds=timeout_seconds,
        runner_script_path=str(Path(__file__).with_name("sandbox_gate_runner.py")),
    )
    try:
        output = await _executor.execute(request)
    except SandboxUnavailableError as exc:
        return {
            "success": False,
            "status": "sandbox_unavailable",
            "logs": "",
            "error": str(exc),
            "checkedAt": None,
            "executionTimeMs": 0,
            "exitCode": None,
            "timedOut": False,
        }

    logs = "\n".join(filter(None, [output.stdout, output.stderr])).strip()
    return {
        "success": output.success,
        "status": "passed" if output.success else "failed",
        "logs": logs,
        "error": output.error_message,
        "checkedAt": datetime.now(timezone.utc).isoformat(),
        "executionTimeMs": output.execution_time_ms,
        "exitCode": output.exit_code,
        "timedOut": output.timed_out,
    }
