import asyncio
import json
import logging
import tempfile
import time
from pathlib import Path

from src.config import settings
from src.sandbox.base import (
    SandboxInput,
    SandboxOutput,
    SandboxUnavailableError,
    ToolRunner,
)

logger = logging.getLogger(__name__)


class DockerExecutor(ToolRunner):
    def __init__(self):
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client

        try:
            import docker
            from docker.errors import DockerException
        except ImportError as exc:
            raise SandboxUnavailableError(
                "Docker SDK is not installed in the current environment."
            ) from exc

        try:
            client = docker.from_env()
            client.ping()
        except DockerException as exc:
            raise SandboxUnavailableError(
                "Docker daemon is unavailable or inaccessible."
            ) from exc

        self._client = client
        return client

    async def execute(self, request: SandboxInput) -> SandboxOutput:
        start_time = time.time()
        try:
            return await asyncio.to_thread(self._execute_sync, request, start_time)
        except SandboxUnavailableError:
            raise

    def _execute_sync(self, request: SandboxInput, start_time: float) -> SandboxOutput:
        client = self._get_client()

        with tempfile.TemporaryDirectory(prefix="theseus-sandbox-") as tmpdir:
            root_dir = Path(tmpdir)
            input_dir = root_dir / "input"
            output_dir = root_dir / "output"
            input_dir.mkdir(parents=True, exist_ok=True)
            output_dir.mkdir(parents=True, exist_ok=True)

            (input_dir / "tool_code.py").write_text(request.tool_code, encoding="utf-8")
            (input_dir / "payload.json").write_text(
                json.dumps(request.payload, ensure_ascii=False),
                encoding="utf-8",
            )

            runner_path = Path(__file__).with_name("sandbox_runner.py")
            (input_dir / "sandbox_runner.py").write_text(
                runner_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            command = ["python", "/sandbox/input/sandbox_runner.py"]
            container = None
            stdout = ""
            stderr = ""
            timed_out = False
            exit_code = None

            try:
                container = client.containers.run(
                    settings.SANDBOX_IMAGE,
                    command=command,
                    detach=True,
                    network_disabled=True,
                    mem_limit=settings.SANDBOX_MEMORY_LIMIT,
                    cpu_period=settings.SANDBOX_CPU_PERIOD,
                    cpu_quota=settings.SANDBOX_CPU_QUOTA,
                    volumes={
                        str(input_dir): {"bind": "/sandbox/input", "mode": "ro"},
                        str(output_dir): {"bind": "/sandbox/output", "mode": "rw"},
                    },
                    working_dir="/sandbox/input",
                    auto_remove=False,
                )

                try:
                    wait_result = container.wait(timeout=request.timeout_seconds)
                    exit_code = wait_result.get("StatusCode")
                except Exception:
                    timed_out = True
                    container.kill()
                    exit_code = -1

                stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
                stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")

                result_path = output_dir / "result.json"
                if timed_out:
                    return SandboxOutput(
                        success=False,
                        stdout=stdout,
                        stderr=stderr,
                        error_message="Execution timeout",
                        exit_code=exit_code,
                        timed_out=True,
                        execution_time_ms=int((time.time() - start_time) * 1000),
                    )

                if not result_path.exists():
                    return SandboxOutput(
                        success=False,
                        stdout=stdout,
                        stderr=stderr,
                        error_message="Sandbox result.json was not produced.",
                        exit_code=exit_code,
                        execution_time_ms=int((time.time() - start_time) * 1000),
                    )

                try:
                    result_payload = json.loads(result_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    return SandboxOutput(
                        success=False,
                        stdout=stdout,
                        stderr=stderr,
                        error_message=f"Invalid sandbox result payload: {exc}",
                        exit_code=exit_code,
                        execution_time_ms=int((time.time() - start_time) * 1000),
                    )

                success = bool(result_payload.get("success"))
                return SandboxOutput(
                    success=success,
                    result=result_payload.get("result") if success else None,
                    stdout=stdout,
                    stderr=stderr,
                    error_message=result_payload.get("error_message"),
                    exit_code=exit_code,
                    timed_out=False,
                    resource_limited=False,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                )
            finally:
                if container is not None:
                    try:
                        keep_failed = settings.SANDBOX_KEEP_FAILED_CONTAINERS
                        if keep_failed and exit_code not in (0, None):
                            logger.warning(
                                "Keeping failed sandbox container for debugging: %s",
                                container.id,
                            )
                        else:
                            container.remove(force=True)
                    except Exception as exc:
                        logger.warning("Failed to cleanup sandbox container: %s", exc)
