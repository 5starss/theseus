"""Theseus lightweight background task manager."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import platform
import signal
import subprocess
import uuid
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Dict, Optional

log = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"
TASK_RECORD_SCHEMA_VERSION = 1


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.getenv(name, str(default))
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


MAX_TASKS = _env_int("THESEUS_TASK_MAX_TASKS", 100)
MAX_OUTPUT_BYTES = _env_int("THESEUS_TASK_OUTPUT_MAX_BYTES", 1_000_000)
TASK_STOP_TIMEOUT_SECONDS = _env_int("THESEUS_TASK_STOP_TIMEOUT_SECONDS", 3)


def _now_iso() -> str:
    return datetime.now().isoformat()


def _task_data_root() -> Path:
    raw = os.getenv("THESEUS_TASK_DATA_DIR")
    if raw:
        return Path(raw).expanduser().resolve()
    base = Path(os.getenv("THESEUS_DATA_DIR", str(Path.home() / ".theseus")))
    return (base.expanduser() / "tasks").resolve()


def _resolve_cwd(cwd: "str | os.PathLike[str] | None") -> Path:
    return Path(cwd or os.getcwd()).expanduser().resolve()


def _normalized_path(path_value: "str | os.PathLike[str]") -> str:
    resolved = str(Path(path_value).expanduser().resolve())
    return resolved.lower() if IS_WINDOWS else resolved


def _workspace_hash(cwd: "str | os.PathLike[str]") -> str:
    normalized = _normalized_path(cwd)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _safe_task_id(task_id: str) -> str:
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
    if not task_id or any(ch not in allowed for ch in task_id):
        raise ValueError(f"Invalid task id: {task_id}")
    return task_id


def _workspace_task_dir(cwd: "str | os.PathLike[str]") -> Path:
    return _task_data_root() / _workspace_hash(cwd)


def _record_path(cwd: "str | os.PathLike[str]", task_id: str) -> Path:
    return _workspace_task_dir(cwd) / f"{_safe_task_id(task_id)}.json"


def _log_path(cwd: "str | os.PathLike[str]", task_id: str) -> Path:
    return _workspace_task_dir(cwd) / f"{_safe_task_id(task_id)}.log"


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def _read_tail(path: Path, max_bytes: int) -> str:
    if not path.exists():
        return "(no output)"
    with path.open("rb") as handle:
        handle.seek(0, os.SEEK_END)
        size = handle.tell()
        handle.seek(max(0, size - max_bytes))
        data = handle.read(max_bytes)
    text = data.decode("utf-8", errors="replace").replace("\r\n", "\n").strip()
    return text if text else "(no output)"


def _is_pid_running(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    if IS_WINDOWS:
        try:
            import ctypes
            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32
            process_query = 0x1000
            synchronize = 0x00100000
            still_active = 259
            kernel32.OpenProcess.argtypes = [
                wintypes.DWORD,
                wintypes.BOOL,
                wintypes.DWORD,
            ]
            kernel32.OpenProcess.restype = wintypes.HANDLE
            kernel32.GetExitCodeProcess.argtypes = [
                wintypes.HANDLE,
                ctypes.POINTER(wintypes.DWORD),
            ]
            kernel32.GetExitCodeProcess.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel32.CloseHandle.restype = wintypes.BOOL
            handle = kernel32.OpenProcess(
                process_query | synchronize,
                False,
                int(pid),
            )
            if not handle:
                return False
            try:
                exit_code = wintypes.DWORD()
                if not kernel32.GetExitCodeProcess(
                    handle,
                    ctypes.byref(exit_code),
                ):
                    return False
                return exit_code.value == still_active
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _process_identity(pid: int | None) -> str | None:
    if not pid or pid <= 0:
        return None
    if IS_WINDOWS:
        return _windows_process_identity(pid)

    proc_stat = Path(f"/proc/{pid}/stat")
    if not proc_stat.exists():
        return None
    try:
        text = proc_stat.read_text(encoding="utf-8", errors="replace")
        fields_after_name = text.rsplit(") ", 1)[1].split()
        return f"proc-start:{fields_after_name[19]}"
    except (IndexError, OSError):
        return None


def _pid_matches_recorded_identity(task: "TaskInfo", pid: int | None) -> bool:
    expected = task.metadata.get("process_identity")
    if not expected:
        return True
    return _process_identity(pid) == expected


@dataclass
class TaskInfo:
    """A background task and its local process metadata."""

    id: str
    type: str  # "shell"
    description: str
    status: str = "running"  # running | completed | failed | stopped | exited
    command: Optional[str] = None
    cwd: Optional[str] = None
    pid: Optional[int] = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    log_path: Optional[str] = None
    record_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    _process: Optional[asyncio.subprocess.Process] = field(default=None, repr=False)
    _output_buffer: bytearray = field(default_factory=bytearray, repr=False)
    _log_handle: Optional[BinaryIO] = field(default=None, repr=False)

    def __str__(self) -> str:
        pid_text = f", pid={self.pid}" if self.pid else ""
        return (
            f"Task(id={self.id}, type={self.type}, status={self.status}{pid_text}, "
            f"desc={self.description!r}, created={self.created_at})"
        )

    def to_record(self) -> dict[str, Any]:
        return {
            "schemaVersion": TASK_RECORD_SCHEMA_VERSION,
            "id": self.id,
            "type": self.type,
            "description": self.description,
            "status": self.status,
            "command": self.command,
            "cwd": self.cwd,
            "pid": self.pid,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "logPath": self.log_path,
            "metadata": self.metadata,
            "workspaceHash": _workspace_hash(self.cwd or os.getcwd()),
        }


class TheseusTaskManager:
    """In-process and recoverable background task manager."""

    def __init__(self) -> None:
        self._tasks: Dict[str, TaskInfo] = {}

    async def create_shell_task(
        self,
        command: str,
        description: str,
        cwd: "str | os.PathLike[str] | None" = None,
    ) -> TaskInfo:
        """Run a shell command in the background."""
        workspace = _resolve_cwd(cwd)
        self._load_workspace_records(workspace)
        self._prune_terminal_tasks(reserve_slot=True)
        if len(self._tasks) >= MAX_TASKS:
            raise ValueError("Background task limit exceeded.")

        task_id = uuid.uuid4().hex[:8]
        task_dir = _workspace_task_dir(workspace)
        task_dir.mkdir(parents=True, exist_ok=True)
        log_file = _log_path(workspace, task_id)
        record_file = _record_path(workspace, task_id)
        log_handle = log_file.open("ab", buffering=0)

        try:
            if IS_WINDOWS:
                creationflags = (
                    getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
                    | getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
                process = await asyncio.create_subprocess_exec(
                    "cmd.exe",
                    "/c",
                    command,
                    cwd=str(workspace),
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=log_handle,
                    stderr=asyncio.subprocess.STDOUT,
                    creationflags=creationflags,
                )
            else:
                process = await asyncio.create_subprocess_shell(
                    command,
                    cwd=str(workspace),
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=log_handle,
                    stderr=asyncio.subprocess.STDOUT,
                    start_new_session=True,
                )
        except Exception:
            log_handle.close()
            raise

        task = TaskInfo(
            id=task_id,
            type="shell",
            description=description,
            command=command,
            cwd=str(workspace),
            pid=process.pid,
            log_path=str(log_file),
            record_path=str(record_file),
            metadata={
                "workspace_hash": _workspace_hash(workspace),
                "process_identity": _process_identity(process.pid),
            },
            _process=process,
            _log_handle=log_handle,
        )
        self._tasks[task_id] = task
        self._save_task_record(task)

        asyncio.create_task(self._watch(task))
        log.info("Background task created: %s (%s)", task_id, description)
        return task

    async def _watch(self, task: TaskInfo) -> None:
        """Watch a task process and persist its terminal status."""
        proc = task._process
        if proc is None:
            return
        try:
            if proc.stdout is not None:
                await self._capture_stream(task, proc.stdout)
            await proc.wait()
            if task.metadata.get("stop_requested_at"):
                task.status = "stopped"
            elif proc.returncode == 0:
                task.status = "completed"
            else:
                task.status = "failed"
            task.updated_at = _now_iso()
            self._save_task_record(task)
            self._prune_terminal_tasks()
        except Exception as e:
            log.warning("Task %s watcher error: %s", task.id, e)
            task.status = "failed"
            task.updated_at = _now_iso()
            self._save_task_record(task)
        finally:
            self._close_log_handle(task)

    async def _capture_stream(self, task: TaskInfo, stream: asyncio.StreamReader) -> None:
        while True:
            chunk = await stream.read(4096)
            if not chunk:
                break
            task._output_buffer.extend(chunk)
            overflow = len(task._output_buffer) - MAX_OUTPUT_BYTES
            if overflow > 0:
                del task._output_buffer[:overflow]
                task.metadata["output_truncated"] = True
            if task._log_handle is not None:
                task._log_handle.write(chunk)

    def list_tasks(
        self,
        status: Optional[str] = None,
        cwd: "str | os.PathLike[str] | None" = None,
    ) -> list[TaskInfo]:
        """Return registered background tasks."""
        workspace = _resolve_cwd(cwd) if cwd is not None else None
        if workspace is not None:
            self._load_workspace_records(workspace)

        tasks = list(self._tasks.values())
        if workspace is not None:
            workspace_key = _workspace_hash(workspace)
            tasks = [
                t for t in tasks
                if t.cwd and _workspace_hash(t.cwd) == workspace_key
            ]
        for task in tasks:
            self._sync_task_liveness(task)
        if status:
            tasks = [t for t in tasks if t.status == status]
        return tasks

    def get_task(
        self,
        task_id: str,
        cwd: "str | os.PathLike[str] | None" = None,
    ) -> Optional[TaskInfo]:
        """Return a specific background task."""
        task = self._tasks.get(task_id)
        if task is None and cwd is not None:
            task = self._load_task_record(task_id, _resolve_cwd(cwd))
        if task is not None:
            self._sync_task_liveness(task)
        return task

    def read_task_output(
        self,
        task_id: str,
        max_bytes: int = 12000,
        cwd: "str | os.PathLike[str] | None" = None,
    ) -> str:
        """Read a task's persisted output."""
        task = self.get_task(task_id, cwd=cwd)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        if task.log_path:
            return _read_tail(Path(task.log_path), max_bytes)
        text = (
            task._output_buffer[-max_bytes:]
            .decode("utf-8", errors="replace")
            .replace("\r\n", "\n")
            .strip()
        )
        return text if text else "(no output)"

    async def stop_task(
        self,
        task_id: str,
        cwd: "str | os.PathLike[str] | None" = None,
    ) -> TaskInfo:
        """Stop a running task by killing its process tree."""
        task = self.get_task(task_id, cwd=cwd)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")

        task.metadata["stop_requested_at"] = _now_iso()
        task.updated_at = _now_iso()
        self._save_task_record(task)

        pid = task.pid or (task._process.pid if task._process else None)
        if task._process is not None and task._process.returncode is not None:
            stopped = True
        elif pid and _is_pid_running(pid):
            if not _pid_matches_recorded_identity(task, pid):
                task.status = "exited"
                task.metadata["stop_error"] = (
                    "Stored PID no longer matches the recorded task process."
                )
                task.updated_at = _now_iso()
                self._save_task_record(task)
                return task
            stopped = await _terminate_process_tree(task._process, pid)
        else:
            stopped = True

        task.status = "stopped" if stopped else "failed"
        if not stopped:
            task.metadata["stop_error"] = "Process did not exit after forced termination."
        task.updated_at = _now_iso()
        self._save_task_record(task)
        self._close_log_handle(task)
        return task

    def update_task(
        self,
        task_id: str,
        description: Optional[str] = None,
        progress: Optional[int] = None,
        status_note: Optional[str] = None,
    ) -> TaskInfo:
        """Update task metadata."""
        task = self._tasks.get(task_id)
        if task is None:
            raise ValueError(f"Task not found: {task_id}")
        if description is not None:
            task.description = description
        if progress is not None:
            task.metadata["progress"] = progress
        if status_note is not None:
            task.metadata["status_note"] = status_note
        task.updated_at = _now_iso()
        self._save_task_record(task)
        return task

    def _load_workspace_records(self, cwd: "str | os.PathLike[str]") -> None:
        task_dir = _workspace_task_dir(cwd)
        if not task_dir.exists():
            return
        for path in task_dir.glob("*.json"):
            record = _read_json(path)
            if record is None:
                continue
            task = self._task_from_record(record, path, cwd)
            if task is not None and task.id not in self._tasks:
                self._tasks[task.id] = task

    def _load_task_record(
        self,
        task_id: str,
        cwd: "str | os.PathLike[str]",
    ) -> Optional[TaskInfo]:
        try:
            path = _record_path(cwd, task_id)
        except ValueError:
            return None
        record = _read_json(path)
        if record is None:
            return None
        task = self._task_from_record(record, path, cwd)
        if task is not None:
            self._tasks[task.id] = task
        return task

    def _task_from_record(
        self,
        record: dict[str, Any],
        path: Path,
        cwd: "str | os.PathLike[str]",
    ) -> Optional[TaskInfo]:
        if record.get("schemaVersion") != TASK_RECORD_SCHEMA_VERSION:
            return None
        task_id = record.get("id")
        record_cwd = record.get("cwd")
        if not isinstance(task_id, str) or not isinstance(record_cwd, str):
            return None
        if _workspace_hash(record_cwd) != _workspace_hash(cwd):
            return None

        metadata = record.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        task = TaskInfo(
            id=task_id,
            type=str(record.get("type") or "shell"),
            description=str(record.get("description") or ""),
            status=str(record.get("status") or "running"),
            command=(
                record.get("command")
                if isinstance(record.get("command"), str)
                else None
            ),
            cwd=record_cwd,
            pid=int(record["pid"]) if isinstance(record.get("pid"), int) else None,
            created_at=str(record.get("createdAt") or _now_iso()),
            updated_at=str(record.get("updatedAt") or _now_iso()),
            log_path=(
                record.get("logPath")
                if isinstance(record.get("logPath"), str)
                else None
            ),
            record_path=str(path),
            metadata=metadata,
        )
        self._sync_task_liveness(task)
        return task

    def _sync_task_liveness(self, task: TaskInfo) -> None:
        if task.status != "running":
            return
        if task._process is not None:
            if task._process.returncode is None:
                return
            task.status = "completed" if task._process.returncode == 0 else "failed"
        elif (
            not _is_pid_running(task.pid)
            or not _pid_matches_recorded_identity(task, task.pid)
        ):
            task.status = "exited"
        else:
            return
        task.updated_at = _now_iso()
        self._save_task_record(task)

    def _save_task_record(self, task: TaskInfo) -> None:
        if not task.cwd:
            return
        path = (
            Path(task.record_path)
            if task.record_path
            else _record_path(task.cwd, task.id)
        )
        task.record_path = str(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(task.to_record(), indent=2), encoding="utf-8")
        tmp.replace(path)

    def _close_log_handle(self, task: TaskInfo) -> None:
        handle = task._log_handle
        task._log_handle = None
        if handle is not None:
            with suppress(Exception):
                handle.close()

    def _prune_terminal_tasks(self, *, reserve_slot: bool = False) -> None:
        overflow = len(self._tasks) - MAX_TASKS + (1 if reserve_slot else 0)
        if overflow <= 0:
            return
        removable = [
            task_id for task_id, task in self._tasks.items()
            if task.status in {"completed", "failed", "stopped", "exited"}
        ]
        for task_id in removable[:overflow]:
            self._tasks.pop(task_id, None)


async def _terminate_process_tree(
    proc: asyncio.subprocess.Process | None,
    pid: int,
) -> bool:
    if IS_WINDOWS:
        await _taskkill(pid, force=False)
        if await _wait_for_exit(proc, pid, TASK_STOP_TIMEOUT_SECONDS):
            return True
        if proc is not None and proc.returncode is None:
            with suppress(ProcessLookupError):
                proc.terminate()
        if await _wait_for_exit(proc, pid, 1.0):
            return True
        await _taskkill(pid, force=True)
        if await _wait_for_exit(proc, pid, 2.0):
            return True
        _terminate_windows_process_tree(pid)
        if await _wait_for_exit(proc, pid, 2.0):
            return True
        if proc is not None and proc.returncode is None:
            with suppress(ProcessLookupError):
                proc.kill()
        return await _wait_for_exit(proc, pid, 2.0)

    try:
        pgid = os.getpgid(pid)
    except OSError:
        pgid = None

    if pgid is not None:
        with suppress(ProcessLookupError, PermissionError, OSError):
            os.killpg(pgid, signal.SIGTERM)
    elif proc is not None and proc.returncode is None:
        with suppress(ProcessLookupError):
            proc.terminate()

    if await _wait_for_exit(proc, pid, TASK_STOP_TIMEOUT_SECONDS):
        return True

    if pgid is not None:
        with suppress(ProcessLookupError, PermissionError, OSError):
            os.killpg(pgid, signal.SIGKILL)
    elif proc is not None and proc.returncode is None:
        with suppress(ProcessLookupError):
            proc.kill()
    return await _wait_for_exit(proc, pid, 2.0)


async def _taskkill(pid: int, *, force: bool) -> None:
    args = ["taskkill", "/PID", str(pid), "/T"]
    if force:
        args.append("/F")
    try:
        process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        await asyncio.wait_for(process.communicate(), timeout=5.0)
    except Exception as exc:
        log.debug("taskkill failed for pid=%s force=%s: %s", pid, force, exc)


def _terminate_windows_process_tree(root_pid: int) -> None:
    if not IS_WINDOWS:
        return
    descendants = _windows_descendant_pids(root_pid)
    for pid in list(reversed(descendants)) + [root_pid]:
        _terminate_windows_pid(pid)


def _windows_descendant_pids(root_pid: int) -> list[int]:
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return []

    max_path = 260
    th32cs_snapprocess = 0x00000002
    invalid_handle_value = ctypes.c_void_p(-1).value

    class ProcessEntry32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.c_void_p),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * max_path),
        ]

    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel32.Process32FirstW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessEntry32W),
    ]
    kernel32.Process32FirstW.restype = wintypes.BOOL
    kernel32.Process32NextW.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessEntry32W),
    ]
    kernel32.Process32NextW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    snapshot = kernel32.CreateToolhelp32Snapshot(th32cs_snapprocess, 0)
    if snapshot == invalid_handle_value:
        return []

    parent_map: dict[int, list[int]] = {}
    try:
        entry = ProcessEntry32W()
        entry.dwSize = ctypes.sizeof(ProcessEntry32W)
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            parent = int(entry.th32ParentProcessID)
            child = int(entry.th32ProcessID)
            parent_map.setdefault(parent, []).append(child)
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)

    descendants: list[int] = []
    stack = list(parent_map.get(root_pid, []))
    seen: set[int] = set()
    while stack:
        pid = stack.pop()
        if pid in seen:
            continue
        seen.add(pid)
        descendants.append(pid)
        stack.extend(parent_map.get(pid, []))
    return descendants


def _windows_process_identity(pid: int) -> str | None:
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return None

    class FileTime(ctypes.Structure):
        _fields_ = [
            ("dwLowDateTime", wintypes.DWORD),
            ("dwHighDateTime", wintypes.DWORD),
        ]

    process_query = 0x1000
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime),
    ]
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    handle = kernel32.OpenProcess(process_query, False, int(pid))
    if not handle:
        return None
    try:
        created = FileTime()
        exited = FileTime()
        kernel = FileTime()
        user = FileTime()
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(created),
            ctypes.byref(exited),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            return None
        created_ticks = (int(created.dwHighDateTime) << 32) | int(created.dwLowDateTime)
        return f"win-start:{created_ticks}"
    finally:
        kernel32.CloseHandle(handle)


def _terminate_windows_pid(pid: int) -> bool:
    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return False

    process_terminate = 0x0001
    synchronize = 0x00100000
    kernel32 = ctypes.windll.kernel32
    kernel32.OpenProcess.argtypes = [
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.TerminateProcess.argtypes = [wintypes.HANDLE, wintypes.UINT]
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(
        process_terminate | synchronize,
        False,
        int(pid),
    )
    if not handle:
        return False
    try:
        return bool(kernel32.TerminateProcess(handle, 1))
    finally:
        kernel32.CloseHandle(handle)


async def _wait_for_exit(
    proc: asyncio.subprocess.Process | None,
    pid: int,
    timeout: float,
) -> bool:
    if proc is not None:
        if proc.returncode is not None:
            return True
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if not _is_pid_running(pid):
            return True
        await asyncio.sleep(0.1)
    return not _is_pid_running(pid)


_manager: Optional[TheseusTaskManager] = None
_manager_lock = __import__("threading").Lock()


def get_task_manager() -> TheseusTaskManager:
    """Return the process-wide task manager singleton."""
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = TheseusTaskManager()
    return _manager
