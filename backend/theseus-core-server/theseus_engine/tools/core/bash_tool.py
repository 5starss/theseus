"""Shell command execution tool for Theseus agent."""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Iterable

from pydantic import BaseModel, Field

from theseus_engine.tools.core.base_tools import BaseTool, ToolExecutionContext, ToolResult
from theseus_engine.tools.core.file_utils import _check_path_security

log = logging.getLogger(__name__)


class BashInput(BaseModel):
    """Arguments for the bash tool."""

    command: str = Field(description="Shell command to execute")
    cwd: str | None = Field(
        default=None, description="Working directory override"
    )
    timeout_seconds: int = Field(default=120, ge=1, le=600)


class BashTool(BaseTool):
    """Execute a shell command with stdout/stderr capture."""

    name = "bash"
    description = (
        "Run a shell command in the local workspace. "
        "Returns stdout and stderr. "
        "IMPORTANT: Do NOT run interactive commands (e.g. npm init without -y). "
        "Use non-interactive flags like --yes, -y, --defaults. "
        "Do NOT launch background or long-running processes here; use task_create "
        "so task_stop can reliably stop them."
    )
    input_model = BashInput
    permission_level = 3  # 높은 권한 — 셸 접근
    is_destructive = True  # 셸 실행 — 항상 파괴적 가능성

    def is_read_only(self, arguments) -> bool:
        return False

    async def execute(
        self, arguments: BashInput, context: ToolExecutionContext
    ) -> ToolResult:
        if arguments.cwd:
            cwd = Path(arguments.cwd).expanduser()
            if not cwd.is_absolute():
                cwd = (context.cwd / cwd).resolve()
            else:
                cwd = cwd.resolve()
            security_err = _check_path_security(cwd, context.cwd)
            if security_err:
                return ToolResult(output=security_err, is_error=True)
        else:
            cwd = context.cwd

        # 대화형 명령어 사전 차단
        preflight = _preflight_interactive(arguments.command)
        if preflight is not None:
            return ToolResult(output=preflight, is_error=True)

        try:
            process = await asyncio.create_subprocess_shell(
                arguments.command,
                cwd=str(cwd),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        except Exception as exc:
            return ToolResult(
                output=f"Command execution failed: {exc}", is_error=True
            )

        try:
            try:
                await asyncio.wait_for(
                    process.wait(), timeout=arguments.timeout_seconds
                )
            except asyncio.TimeoutError:
                buf = await _drain(process.stdout)
                await _terminate(process, force=True)
                buf.extend(await _read_remaining(process))
                return ToolResult(
                    output=_fmt_timeout(
                        buf,
                        command=arguments.command,
                        timeout=arguments.timeout_seconds,
                    ),
                    is_error=True,
                )
        except asyncio.CancelledError:
            await _terminate(process, force=True)
            raise

        buf = await _read_remaining(process)
        text = _fmt_output(buf)
        return ToolResult(
            output=text,
            is_error=process.returncode != 0,
            metadata={"returncode": process.returncode},
        )


# ── helpers ──────────────────────────────────────────────────────


async def _terminate(
    proc: asyncio.subprocess.Process, *, force: bool
) -> None:
    if proc.returncode is not None:
        return
    if force:
        proc.kill()
        await proc.wait()
        return
    proc.terminate()
    try:
        await asyncio.wait_for(proc.wait(), timeout=2.0)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()


async def _read_remaining(
    proc: asyncio.subprocess.Process,
) -> bytearray:
    buf = bytearray()
    if proc.stdout is not None:
        buf.extend(await proc.stdout.read())
    return buf


async def _drain(
    stream: asyncio.StreamReader | None,
    *,
    read_timeout: float = 0.05,
) -> bytearray:
    buf = bytearray()
    if stream is None:
        return buf
    while True:
        try:
            chunk = await asyncio.wait_for(
                stream.read(65536), timeout=read_timeout
            )
        except asyncio.TimeoutError:
            return buf
        if not chunk:
            return buf
        buf.extend(chunk)


def _fmt_output(buf: bytearray) -> str:
    text = (
        buf.decode("utf-8", errors="replace")
        .replace("\r\n", "\n")
        .strip()
    )
    if not text:
        return "(no output)"
    if len(text) > 12000:
        return f"{text[:12000]}\n...[truncated]..."
    return text


def _fmt_timeout(
    buf: bytearray, *, command: str, timeout: int
) -> str:
    parts = [f"Command timed out after {timeout} seconds."]
    text = _fmt_output(buf)
    if text != "(no output)":
        parts.extend(["", "Partial output:", text])
    return "\n".join(parts)


def _preflight_interactive(command: str) -> str | None:
    low = command.lower()
    background_markers = (
        "start-process", "start-job", "nohup ", "disown",
        "setsid ", "start /b",
    )
    if any(m in low for m in background_markers) or re.search(r"(?<!&)&\s*$", command):
        return (
            "This command appears to launch a background process. "
            "Use task_create instead so Theseus records the PID and task_stop "
            "can stop the process tree later."
        )

    scaffold_markers = (
        "create-next-app", "npm create ", "pnpm create ",
        "yarn create ", "bun create ", "pnpm dlx ",
        "npm init ", "pnpm init ", "yarn init ",
        "bunx create-", "npx create-",
    )
    safe_markers = (
        "--yes", " -y", "--skip-install",
        "--defaults", "--non-interactive", "--ci",
    )
    if any(m in low for m in scaffold_markers) and not any(
        m in low for m in safe_markers
    ):
        return (
            "This command requires interactive input. "
            "The bash tool is non-interactive — add flags like "
            "--yes / -y / --defaults, or run in an external terminal."
        )
    return None
