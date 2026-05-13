"""Local HTTP/SSE daemon for VSCode and other editor clients."""

from __future__ import annotations

import argparse
import asyncio
import contextvars
import hashlib
import json
import os
import secrets
import socket
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from theseus_engine.runner_runtime import EditorRuntime


RUNNER_STATE_SCHEMA_VERSION = 1
TERMINAL_RUN_STATUSES = {"completed", "interrupted", "error"}


def _env_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw = os.getenv(name, str(default))
    try:
        return max(minimum, int(raw))
    except ValueError:
        return default


MAX_RUNS = _env_int("THESEUS_DAEMON_MAX_RUNS", 50)
MAX_EVENTS_PER_RUN = _env_int("THESEUS_DAEMON_MAX_EVENTS_PER_RUN", 1000)
PERMISSION_RESPONSE_TIMEOUT_SECONDS = _env_int(
    "THESEUS_PERMISSION_RESPONSE_TIMEOUT_SECONDS",
    300,
)


class DaemonBusyError(RuntimeError):
    """Raised when a local daemon already has an active run."""


def workspace_hash(workspace: Path) -> str:
    normalized = os.path.normcase(str(workspace.resolve()))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


@dataclass
class RunState:
    run_id: str
    text: str
    status: str = "queued"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    events: list[dict[str, Any]] = field(default_factory=list)
    event_offset: int = 0
    condition: asyncio.Condition = field(default_factory=asyncio.Condition)
    task: asyncio.Task[None] | None = None
    interrupt_requested: bool = False


@dataclass
class PermissionWaiter:
    run_id: str
    future: asyncio.Future[bool]
    created_at: float = field(default_factory=time.time)


class RunRequest(BaseModel):
    text: str
    mode: str | None = None


class PermissionResponseRequest(BaseModel):
    approved: bool


class DaemonState:
    def __init__(
        self,
        *,
        workspace: Path,
        token: str,
        model: str,
        user_level: int,
        session_id: str | None = None,
        initial_session: str = "default",
        workspace_hash_value: str | None = None,
        runtime_factory: Callable[[], EditorRuntime] | None = None,
    ) -> None:
        self.workspace = workspace
        self.token = token
        self.session_id = session_id or f"daemon-{int(time.time() * 1000)}-{secrets.token_hex(4)}"
        self.workspace_hash = workspace_hash_value or workspace_hash(workspace)
        self.started_at = time.time()
        self.runs: dict[str, RunState] = {}
        self.permission_waiters: dict[str, PermissionWaiter] = {}
        self._permission_run: contextvars.ContextVar[RunState | None] = (
            contextvars.ContextVar("theseus_permission_run", default=None)
        )
        self.initialized = False
        self.last_event_at: float | None = None
        self._lock = asyncio.Lock()
        self.runtime = runtime_factory() if runtime_factory else EditorRuntime(
            model=model,
            user_level=user_level,
            cwd=workspace,
            initial_session=initial_session,
            permission_prompt=self.permission_prompt,
        )

    async def initialize(self) -> list[dict[str, Any]]:
        if self.initialized:
            return []
        async with self._lock:
            if self.initialized:
                return []
            events = await self.runtime.initialize()
            self.initialized = True
            self.last_event_at = time.time()
            return events

    def status(self) -> dict[str, Any]:
        return {
            "schemaVersion": RUNNER_STATE_SCHEMA_VERSION,
            "mode": "local-daemon",
            "pid": os.getpid(),
            "model": getattr(self.runtime, "model", None),
            "sessionId": self.session_id,
            "workspaceHash": self.workspace_hash,
            "workspaceCwd": str(self.workspace),
            "startedAt": self.started_at,
            "lastEventAt": self.last_event_at,
            "session": getattr(getattr(self.runtime, "sessions", None), "current_name", "default"),
            "runs": [
                {
                    "runId": run.run_id,
                    "status": run.status,
                    "createdAt": run.created_at,
                    "updatedAt": run.updated_at,
                    "eventCount": run.event_offset + len(run.events),
                    "eventOffset": run.event_offset,
                    "interruptRequested": run.interrupt_requested,
                }
                for run in self.runs.values()
            ],
        }

    async def start_run(self, request: RunRequest) -> RunState:
        await self.initialize()
        async with self._lock:
            active = self._active_run()
            if active is not None:
                raise DaemonBusyError(
                    f"이미 실행 중인 run이 있습니다: {active.run_id}"
                )
            self._prune_runs()
            run = RunState(
                run_id=(
                    f"run-{int(time.time() * 1000)}-{secrets.token_hex(4)}"
                ),
                text=request.text,
            )
            self.runs[run.run_id] = run
            run.task = asyncio.create_task(self._execute_run(run, request.mode))
            return run

    async def _execute_run(self, run: RunState, mode: str | None) -> None:
        await self._set_run_status(run, "running")
        permission_token = self._permission_run.set(run)
        try:
            if mode:
                if hasattr(self.runtime, "set_mode"):
                    for event in self.runtime.set_mode(mode, announce=False):
                        await self._append(run, event)
                else:
                    async for event in self.runtime.submit(json.dumps({"type": "setMode", "mode": mode})):
                        await self._append(run, event)
            async for event in self.runtime.submit(run.text):
                await self._append(run, event)
                if run.interrupt_requested:
                    break
            await self._set_run_status(run, "interrupted" if run.interrupt_requested else "completed")
        except asyncio.CancelledError:
            await self._set_run_status(run, "interrupted")
            raise
        except Exception as exc:
            await self._append(run, {"type": "ErrorEvent", "message": str(exc), "recoverable": True, "error_type": "unknown"})
            await self._set_run_status(run, "error")
        finally:
            self._permission_run.reset(permission_token)
            await self._notify_run(run)
            self._prune_runs()

    async def permission_prompt(self, tool_name: str, prompt_msg: str) -> bool:
        run = self._permission_run.get()
        if run is None:
            return False
        request_id = f"perm-{int(time.time() * 1000)}-{secrets.token_hex(4)}"
        future: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self.permission_waiters[request_id] = PermissionWaiter(
            run_id=run.run_id,
            future=future,
        )
        await self._append(
            run,
            {
                "type": "PermissionRequest",
                "request_id": request_id,
                "run_id": run.run_id,
                "tool_name": tool_name,
                "message": prompt_msg,
                "timeout_seconds": PERMISSION_RESPONSE_TIMEOUT_SECONDS,
            },
        )
        try:
            return bool(
                await asyncio.wait_for(
                    future,
                    timeout=PERMISSION_RESPONSE_TIMEOUT_SECONDS,
                )
            )
        except asyncio.TimeoutError:
            await self._append(
                run,
                {
                    "type": "StatusEvent",
                    "message": "권한 승인 응답 시간이 초과되어 도구 실행을 거부했습니다.",
                },
            )
            return False
        finally:
            self.permission_waiters.pop(request_id, None)

    def resolve_permission(
        self,
        run_id: str,
        request_id: str,
        approved: bool,
    ) -> None:
        waiter = self.permission_waiters.get(request_id)
        if waiter is None or waiter.run_id != run_id:
            raise KeyError(request_id)
        if not waiter.future.done():
            waiter.future.set_result(bool(approved))

    async def _append(self, run: RunState, event: dict[str, Any]) -> None:
        self.last_event_at = time.time()
        async with run.condition:
            run.updated_at = self.last_event_at
            run.events.append(event)
            overflow = len(run.events) - MAX_EVENTS_PER_RUN
            if overflow > 0:
                del run.events[:overflow]
                run.event_offset += overflow
            run.condition.notify_all()

    async def _set_run_status(self, run: RunState, status: str) -> None:
        async with run.condition:
            run.status = status
            run.updated_at = time.time()
            run.condition.notify_all()

    async def _notify_run(self, run: RunState) -> None:
        async with run.condition:
            run.updated_at = time.time()
            run.condition.notify_all()

    def interrupt(self, run_id: str) -> RunState:
        run = self.runs.get(run_id)
        if not run:
            raise KeyError(run_id)
        run.interrupt_requested = True
        if run.task and not run.task.done():
            run.task.cancel()
        run.updated_at = time.time()
        return run

    def _active_run(self) -> RunState | None:
        for run in self.runs.values():
            if run.status not in TERMINAL_RUN_STATUSES:
                return run
        return None

    def _prune_runs(self) -> None:
        overflow = len(self.runs) - MAX_RUNS
        if overflow <= 0:
            return
        removable = [
            run_id for run_id, run in self.runs.items()
            if run.status in TERMINAL_RUN_STATUSES
        ]
        for run_id in removable[:overflow]:
            self.runs.pop(run_id, None)


def _auth_dependency(state: DaemonState):
    async def require_auth(authorization: str | None = Header(default=None)) -> None:
        expected = f"Bearer {state.token}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Invalid daemon token")

    return require_auth


def create_app(state: DaemonState) -> FastAPI:
    app = FastAPI(title="Theseus Local Daemon")
    require_auth = _auth_dependency(state)

    @app.on_event("startup")
    async def startup() -> None:
        await state.initialize()

    @app.get("/health", dependencies=[Depends(require_auth)])
    async def health() -> dict[str, Any]:
        return {
            "ok": True,
            "schemaVersion": RUNNER_STATE_SCHEMA_VERSION,
            "mode": "local-daemon",
            "pid": os.getpid(),
            "sessionId": state.session_id,
            "workspaceHash": state.workspace_hash,
            "workspaceCwd": str(state.workspace),
            "startedAt": state.started_at,
        }

    @app.get("/status", dependencies=[Depends(require_auth)])
    async def status() -> dict[str, Any]:
        return state.status()

    @app.post("/runs", dependencies=[Depends(require_auth)])
    async def runs(request: RunRequest) -> dict[str, str]:
        if not request.text.strip():
            raise HTTPException(status_code=400, detail="text is required")
        try:
            run = await state.start_run(request)
        except DaemonBusyError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return {"runId": run.run_id}

    @app.get("/runs/{run_id}/events", dependencies=[Depends(require_auth)])
    async def run_events(run_id: str, after: int = 0):
        run = state.runs.get(run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        async def generate():
            next_index = max(after, run.event_offset)
            while True:
                next_index = max(next_index, run.event_offset)
                event_count = run.event_offset + len(run.events)
                while next_index < event_count:
                    event = run.events[next_index - run.event_offset]
                    next_index += 1
                    yield {
                        "event": "message",
                        "id": str(next_index),
                        "data": json.dumps(event, ensure_ascii=False),
                    }
                if run.status in TERMINAL_RUN_STATUSES:
                    break
                async with run.condition:
                    event_count = run.event_offset + len(run.events)
                    if (
                        next_index >= event_count
                        and run.status not in TERMINAL_RUN_STATUSES
                    ):
                        await run.condition.wait()

        return EventSourceResponse(generate())

    @app.post("/runs/{run_id}/interrupt", dependencies=[Depends(require_auth)])
    async def interrupt(run_id: str) -> JSONResponse:
        try:
            run = state.interrupt(run_id)
        except KeyError:
            raise HTTPException(status_code=404, detail="Run not found")
        return JSONResponse({"runId": run.run_id, "status": run.status, "interruptRequested": True})

    @app.post("/runs/{run_id}/permissions/{request_id}", dependencies=[Depends(require_auth)])
    async def permission_response(
        run_id: str,
        request_id: str,
        request: PermissionResponseRequest,
    ) -> JSONResponse:
        try:
            state.resolve_permission(run_id, request_id, request.approved)
        except KeyError:
            raise HTTPException(status_code=404, detail="권한 요청을 찾을 수 없습니다.")
        return JSONResponse(
            {
                "runId": run_id,
                "requestId": request_id,
                "approved": request.approved,
            }
        )

    return app


def runner_state_path(workspace: Path) -> Path:
    return workspace / ".theseus" / "runner.json"


def write_runner_state(workspace: Path, payload: dict[str, Any]) -> None:
    path = runner_state_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def remove_runner_state(workspace: Path, pid: int) -> None:
    path = runner_state_path(workspace)
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if int(data.get("pid", 0)) not in {0, pid}:
                return
        path.unlink(missing_ok=True)
    except Exception:
        path.unlink(missing_ok=True)


def _bind_local_socket(host: str, port: int) -> socket.socket:
    if host != "127.0.0.1":
        raise ValueError("Theseus local daemon only supports host=127.0.0.1")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, port))
    sock.listen(socket.SOMAXCONN)
    sock.set_inheritable(True)
    return sock


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Theseus local daemon")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--core-root", default="")
    parser.add_argument("--token", default="")
    parser.add_argument("--model", default="google/gemini-3.1-pro-preview-customtools")
    parser.add_argument("--user-level", type=int, default=5)
    parser.add_argument("--session", default="default")
    return parser.parse_args(argv)


def resolve_model(arg_model: str) -> str:
    model = os.getenv("THESEUS_MODEL") or os.getenv("OPENHARNESS_MODEL") or arg_model
    os.environ["THESEUS_MODEL"] = model
    os.environ["OPENHARNESS_MODEL"] = model
    return model


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace = Path(args.workspace).resolve()
    token = args.token or secrets.token_urlsafe(32)
    model = resolve_model(args.model)
    session_id = f"daemon-{int(time.time() * 1000)}-{secrets.token_hex(4)}"
    workspace_hash_value = workspace_hash(workspace)
    sock = _bind_local_socket(args.host, args.port)
    actual_port = int(sock.getsockname()[1])
    write_runner_state(
        workspace,
        {
            "schemaVersion": RUNNER_STATE_SCHEMA_VERSION,
            "pid": os.getpid(),
            "port": actual_port,
            "host": args.host,
            "token": token,
            "mode": "local-daemon",
            "model": model,
            "sessionId": session_id,
            "session": args.session or "default",
            "workspaceHash": workspace_hash_value,
            "workspaceCwd": str(workspace),
            "coreRoot": args.core_root,
            "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        },
    )
    state = DaemonState(
        workspace=workspace,
        token=token,
        model=model,
        user_level=args.user_level,
        session_id=session_id,
        initial_session=args.session or "default",
        workspace_hash_value=workspace_hash_value,
    )
    config = uvicorn.Config(create_app(state), host=args.host, port=actual_port, log_level="info")
    server = uvicorn.Server(config)
    try:
        asyncio.run(server.serve(sockets=[sock]))
        return 0
    finally:
        remove_runner_state(workspace, os.getpid())


if __name__ == "__main__":
    raise SystemExit(main())
