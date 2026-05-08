import asyncio
import json
import logging
import tempfile
import time
from pathlib import Path
from typing import Any

from src.config import settings
from src.sandbox.base import (
    SandboxInput,
    SandboxOutput,
    SandboxUnavailableError,
    ToolRunner,
)

logger = logging.getLogger(__name__)


class SandboxStartupCheckError(SandboxUnavailableError):
    """Raised when sandbox prerequisites fail during startup validation."""


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
            client = docker.from_env(environment=self._docker_environment())
            client.ping()
        except DockerException as exc:
            raise SandboxUnavailableError(
                "Docker daemon is unavailable or inaccessible."
            ) from exc

        self._client = client
        return client

    def _docker_environment(self) -> dict[str, str] | None:
        if not settings.docker_host:
            return None
        return {"DOCKER_HOST": settings.docker_host}

    def verify_connectivity(self, *, pull_if_missing: bool = False) -> dict[str, Any]:
        client = self._get_client()
        image = settings.SANDBOX_IMAGE

        try:
            client.images.get(image)
            image_status = "present"
        except Exception as exc:
            if not pull_if_missing:
                raise SandboxStartupCheckError(
                    f"Sandbox image '{image}' is not available locally."
                ) from exc
            try:
                client.images.pull(image)
                image_status = "pulled"
            except Exception as pull_exc:
                raise SandboxStartupCheckError(
                    f"Sandbox image '{image}' could not be pulled."
                ) from pull_exc

        return {
            "dockerHost": settings.docker_host or "local-default",
            "image": image,
            "imageStatus": image_status,
        }

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

            runner_path = (
                Path(request.runner_script_path)
                if request.runner_script_path
                else Path(__file__).with_name("sandbox_runner.py")
            )
            (input_dir / "sandbox_runner.py").write_text(
                runner_path.read_text(encoding="utf-8"),
                encoding="utf-8",
            )

            command = ["python", "/sandbox/input/sandbox_runner.py"]
            container = None
            stdout = ""
            stderr = ""
            timed_out = False
            resource_limited = False
            exit_code = None
            diagnostics: dict[str, Any] = {
                "sandboxImage": settings.SANDBOX_IMAGE,
                "dockerHost": settings.docker_host or "local-default",
                "inputDir": str(input_dir.resolve()),
                "outputDir": str(output_dir.resolve()),
            }

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
                        str(input_dir.resolve()): {"bind": "/sandbox/input", "mode": "ro"},
                        str(output_dir.resolve()): {"bind": "/sandbox/output", "mode": "rw"},
                    },
                    working_dir="/sandbox/input",
                    auto_remove=False,
                )
            except Exception as exc:
                return self._failure_output(
                    start_time,
                    diagnostics=diagnostics,
                    error_type=self._classify_docker_error(exc),
                    error_message=f"Docker container startup failed: {exc}",
                )

            try:
                try:
                    wait_result = container.wait(timeout=request.timeout_seconds)
                    exit_code = wait_result.get("StatusCode")
                except Exception:
                    timed_out = True
                    container.kill()
                    exit_code = -1

                stdout, stderr = self._collect_logs(container)
                diagnostics["containerId"] = container.id
                diagnostics["containerExitCode"] = exit_code
                resource_limited = exit_code == 137
                diagnostics["resourceLimited"] = resource_limited
                if resource_limited:
                    diagnostics["resourceLimitReason"] = "oom_or_sigkill"

                result_path = output_dir / "result.json"
                if timed_out:
                    return self._failure_output(
                        start_time,
                        stdout=stdout,
                        stderr=stderr,
                        error_type="timeout",
                        error_message="Execution timeout",
                        exit_code=exit_code,
                        timed_out=True,
                        diagnostics=diagnostics,
                    )

                if not result_path.exists():
                    return self._failure_output(
                        start_time,
                        stdout=stdout,
                        stderr=stderr,
                        error_type="resource_limit" if resource_limited else "result_missing",
                        error_message=(
                            "Execution stopped due to sandbox resource limits."
                            if resource_limited
                            else "Sandbox result.json was not produced."
                        ),
                        exit_code=exit_code,
                        resource_limited=resource_limited,
                        diagnostics=diagnostics,
                    )

                try:
                    result_payload = json.loads(result_path.read_text(encoding="utf-8"))
                except json.JSONDecodeError as exc:
                    return self._failure_output(
                        start_time,
                        stdout=stdout,
                        stderr=stderr,
                        error_type="invalid_result",
                        error_message=f"Invalid sandbox result payload: {exc}",
                        exit_code=exit_code,
                        diagnostics=diagnostics,
                    )

                success = bool(result_payload.get("success"))
                return SandboxOutput(
                    success=success,
                    result=result_payload.get("result") if success else None,
                    stdout=stdout,
                    stderr=stderr,
                    error_message=result_payload.get("error_message"),
                    error_type=None if success else ("resource_limit" if resource_limited else "sandbox_runner_error"),
                    exit_code=exit_code,
                    timed_out=False,
                    resource_limited=resource_limited,
                    execution_time_ms=int((time.time() - start_time) * 1000),
                    metadata=diagnostics,
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

    def _collect_logs(self, container) -> tuple[str, str]:
        stdout = ""
        stderr = ""
        try:
            stdout = container.logs(stdout=True, stderr=False).decode("utf-8", errors="replace")
        except Exception as exc:
            stdout = f"[log collection failed] {exc}"
        try:
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8", errors="replace")
        except Exception as exc:
            stderr = f"{stderr}\n[stderr collection failed] {exc}".strip()
        return stdout, stderr

    def _classify_docker_error(self, exc: Exception) -> str:
        message = str(exc).lower()
        if "not found" in message or "pull access denied" in message:
            return "image_not_found"
        if "permission denied" in message:
            return "permission_denied"
        if "mount" in message or "bind source path" in message or "invalid volume" in message:
            return "mount_failure"
        if "connection aborted" in message or "failed to establish a new connection" in message:
            return "docker_connection_failed"
        return "docker_error"

    def _failure_output(
        self,
        start_time: float,
        *,
        error_type: str,
        error_message: str,
        stdout: str = "",
        stderr: str = "",
        exit_code: int | None = None,
        timed_out: bool = False,
        resource_limited: bool = False,
        diagnostics: dict[str, Any] | None = None,
    ) -> SandboxOutput:
        return SandboxOutput(
            success=False,
            stdout=stdout,
            stderr=stderr,
            error_message=error_message,
            error_type=error_type,
            exit_code=exit_code,
            timed_out=timed_out,
            resource_limited=resource_limited,
            execution_time_ms=int((time.time() - start_time) * 1000),
            metadata=diagnostics or {},
        )
