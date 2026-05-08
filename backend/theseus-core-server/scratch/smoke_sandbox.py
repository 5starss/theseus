import asyncio
import json
import sys
from pathlib import Path

from src.sandbox.base import SandboxInput
from src.sandbox.docker_executor import DockerExecutor, SandboxUnavailableError


DUMMY_TOOL_CODE = """
def main(payload):
    return {
        "ok": True,
        "tool": payload["tool_name"],
        "module": payload["module_name"],
    }
"""


async def run_smoke_test() -> int:
    executor = DockerExecutor()
    request = SandboxInput(
        project_id="smoke-project",
        tool_name="smoke_tool",
        tool_code=DUMMY_TOOL_CODE,
        payload={
            "tool_name": "smoke_tool",
            "module_name": "smoke-project:smoke_tool",
        },
        timeout_seconds=5,
        runner_script_path=str(
            Path(__file__).resolve().parent.parent / "src" / "tooling" / "sandbox_gate_runner.py"
        ),
    )

    try:
        print("[smoke] verifying sandbox connectivity...")
        connectivity = executor.verify_connectivity()
        print(f"[smoke] docker={connectivity['dockerHost']} image={connectivity['image']} status={connectivity['imageStatus']}")

        print("[smoke] executing dummy tool...")
        result = await executor.execute(request)
    except SandboxUnavailableError as exc:
        print(f"[smoke] sandbox unavailable: {exc}")
        return 2

    print("[smoke] result:")
    print(
        json.dumps(
            {
                "success": result.success,
                "error_type": result.error_type,
                "error_message": result.error_message,
                "exit_code": result.exit_code,
                "timed_out": result.timed_out,
                "resource_limited": result.resource_limited,
                "execution_time_ms": result.execution_time_ms,
                "metadata": result.metadata,
                "result": result.result,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.success else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(run_smoke_test()))
