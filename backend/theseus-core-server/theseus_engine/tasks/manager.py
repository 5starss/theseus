"""Theseus lightweight background task manager.

OpenHarness의 tasks.manager에 의존하지 않고,
asyncio 네이티브로 백그라운드 셸 프로세스를 관리합니다.
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Optional

log = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.getenv(name, str(default))
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


MAX_TASKS = _env_int("THESEUS_TASK_MAX_TASKS", 100)
MAX_OUTPUT_BYTES = _env_int("THESEUS_TASK_OUTPUT_MAX_BYTES", 1_000_000)


@dataclass
class TaskInfo:
    """백그라운드 태스크 하나의 상태 정보."""

    id: str
    type: str  # "shell"
    description: str
    status: str = "running"  # running | completed | failed | stopped
    command: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict = field(default_factory=dict)
    _process: Optional[asyncio.subprocess.Process] = field(
        default=None, repr=False
    )
    _output_buffer: bytearray = field(
        default_factory=bytearray, repr=False
    )

    def __str__(self) -> str:
        return (
            f"Task(id={self.id}, type={self.type}, status={self.status}, "
            f"desc={self.description!r}, created={self.created_at})"
        )


class TheseusTaskManager:
    """인메모리 백그라운드 태스크 매니저 (싱글톤)."""

    def __init__(self) -> None:
        self._tasks: Dict[str, TaskInfo] = {}

    async def create_shell_task(
        self,
        command: str,
        description: str,
        cwd: "str | None" = None,
    ) -> TaskInfo:
        """셸 명령을 백그라운드로 실행합니다."""
        self._prune_terminal_tasks(reserve_slot=True)
        if len(self._tasks) >= MAX_TASKS:
            raise ValueError("백그라운드 태스크 개수 한도를 초과했습니다.")

        task_id = uuid.uuid4().hex[:8]
        cwd_str = str(cwd) if cwd else "."

        if IS_WINDOWS:
            process = await asyncio.create_subprocess_exec(
                "cmd.exe", "/c", command,
                cwd=cwd_str,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )
        else:
            process = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd_str,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
            )

        task = TaskInfo(
            id=task_id,
            type="shell",
            description=description,
            command=command,
            _process=process,
        )
        self._tasks[task_id] = task

        # 백그라운드에서 출력을 수집하고 종료 감지
        asyncio.create_task(self._watch(task))
        log.info("Background task created: %s (%s)", task_id, description)
        return task

    async def _watch(self, task: TaskInfo) -> None:
        """프로세스 종료를 감시하고 출력을 버퍼에 축적합니다."""
        proc = task._process
        if proc is None or proc.stdout is None:
            return
        try:
            while True:
                chunk = await proc.stdout.read(4096)
                if not chunk:
                    break
                task._output_buffer.extend(chunk)
                overflow = len(task._output_buffer) - MAX_OUTPUT_BYTES
                if overflow > 0:
                    del task._output_buffer[:overflow]
                    task.metadata["output_truncated"] = True
            await proc.wait()
            task.status = (
                "completed" if proc.returncode == 0 else "failed"
            )
            self._prune_terminal_tasks()
        except Exception as e:
            log.warning("Task %s watcher error: %s", task.id, e)
            task.status = "failed"

    def list_tasks(
        self, status: Optional[str] = None
    ) -> list[TaskInfo]:
        """등록된 태스크 목록을 반환합니다."""
        tasks = list(self._tasks.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    def get_task(self, task_id: str) -> Optional[TaskInfo]:
        """특정 태스크를 반환합니다."""
        return self._tasks.get(task_id)

    def read_task_output(
        self, task_id: str, max_bytes: int = 12000
    ) -> str:
        """태스크의 출력 버퍼를 읽습니다."""
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(
                f"태스크를 찾을 수 없습니다: {task_id}"
            )
        text = (
            task._output_buffer[-max_bytes:]
            .decode("utf-8", errors="replace")
            .replace("\r\n", "\n")
            .strip()
        )
        return text if text else "(출력 없음)"

    async def stop_task(self, task_id: str) -> TaskInfo:
        """실행 중인 태스크를 중지합니다."""
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(
                f"태스크를 찾을 수 없습니다: {task_id}"
            )
        proc = task._process
        if proc is not None and proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
        task.status = "stopped"
        return task

    def update_task(
        self,
        task_id: str,
        description: Optional[str] = None,
        progress: Optional[int] = None,
        status_note: Optional[str] = None,
    ) -> TaskInfo:
        """태스크 메타데이터를 업데이트합니다."""
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(
                f"태스크를 찾을 수 없습니다: {task_id}"
            )
        if description is not None:
            task.description = description
        if progress is not None:
            task.metadata["progress"] = progress
        if status_note is not None:
            task.metadata["status_note"] = status_note
        return task

    def _prune_terminal_tasks(self, *, reserve_slot: bool = False) -> None:
        overflow = len(self._tasks) - MAX_TASKS + (1 if reserve_slot else 0)
        if overflow <= 0:
            return
        removable = [
            task_id for task_id, task in self._tasks.items()
            if task.status in {"completed", "failed", "stopped"}
        ]
        for task_id in removable[:overflow]:
            self._tasks.pop(task_id, None)


# ── Singleton ────────────────────────────────────────────────────

_manager: Optional[TheseusTaskManager] = None
_manager_lock = __import__("threading").Lock()


def get_task_manager() -> TheseusTaskManager:
    """전역 태스크 매니저 싱글톤을 반환합니다.

    멀티 스레드(FastAPI worker 등) 환경의 레이스 컨디션 방지를 위해
    threading.Lock으로 초기화를 보호합니다.
    """
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = TheseusTaskManager()
    return _manager
