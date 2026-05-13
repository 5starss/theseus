"""Shared editor runtime for stdio and local daemon integrations."""

from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import re
import shlex
import sys
from pathlib import Path
from typing import Any, Callable, Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from theseus_engine.engine.stream_events import ErrorEvent, PlanPhaseTransitionRequested
from theseus_engine.core.plan_flow import (
    PLAN_CONTINUE_PROMPT,
    PLAN_TOOL_ERROR_PROMPT,
    PLAN_VERIFICATION_PROMPT,
    contains_execution_complete,
    contains_verification_complete,
)


DEFAULT_TOOL_PERMISSIONS = {
    "bash": 3,
    "read_file": 1,
    "write_file": 2,
    "edit_file": 2,
    "glob": 1,
    "grep": 1,
    "web_search": 1,
    "web_fetch": 1,
    "dummy_echo": 1,
    "create_tool": 2,
    "system_reboot": 5,
    "search_knowledge_base": 1,
    "ingest_document": 2,
}


PLAN_APPROVAL_RESPONSES = {
    "approve",
    "approved",
    "accept",
    "accepted",
    "ok",
    "okay",
    "yes",
    "y",
    "go",
    "proceed",
    "continue",
    "looks good",
    "승인",
    "승인해",
    "승인해줘",
    "승인합니다",
    "허가",
    "허가해",
    "좋아",
    "좋습니다",
    "진행",
    "진행해",
    "진행해줘",
    "계속",
    "계속해",
}

PLAN_REJECTION_RESPONSES = {
    "reject",
    "rejected",
    "deny",
    "denied",
    "cancel",
    "no",
    "n",
    "거부",
    "반려",
    "취소",
    "중단",
    "안돼",
    "아니",
    "아니요",
}


def classify_plan_review_response(text: str) -> str | None:
    """Return approve/reject for short explicit review decisions."""
    normalized = " ".join(text.strip().strip("\"'`").lower().split())
    normalized = normalized.rstrip(".!?。！？")
    if normalized in PLAN_APPROVAL_RESPONSES:
        return "approve"
    if normalized in PLAN_REJECTION_RESPONSES:
        return "reject"
    return None


def plan_task_counts(plan_json: str) -> dict[str, int]:
    try:
        plan = json.loads(plan_json) if plan_json else {}
    except json.JSONDecodeError:
        plan = {}
    tasks = plan.get("tasks", []) if isinstance(plan, dict) else []
    if not isinstance(tasks, list):
        tasks = []
    done_statuses = {"done", "completed", "complete", "skipped", "cancelled", "canceled"}
    completed = 0
    for task in tasks:
        status = task.get("status") if isinstance(task, dict) else None
        if str(status or "").strip().lower() in done_statuses:
            completed += 1
    total = len(tasks)
    return {
        "totalTasks": total,
        "completedTasks": completed,
        "remainingTasks": max(0, total - completed),
    }


def derive_session_title(prompt: str) -> str:
    """Create a compact display title from the first user request."""
    visible_prompt = prompt.split("\n---\n", 1)[0]
    visible_prompt = " ".join(visible_prompt.strip().split())
    visible_prompt = re.sub(r'@(?:"[^"]+"|[^\s]+)', "", visible_prompt).strip()
    visible_prompt = visible_prompt.strip("\"'`.,!?。！？")
    if not visible_prompt:
        return ""
    if len(visible_prompt) > 42:
        visible_prompt = visible_prompt[:39].rstrip() + "..."
    return visible_prompt


class LocalSessionProvider:
    """Local SessionProvider v1 backed by .theseus_sessions/*.json."""

    source = "local"

    def __init__(self, default_name: str = "default") -> None:
        from theseus_engine.models.sessions import (
            clear_plan_state,
            get_session_path,
            list_sessions,
            load_plan_state,
            load_session_metadata,
            load_session_history,
            save_plan_state,
            save_session_metadata,
            save_session_history,
        )

        self._clear_plan_state = clear_plan_state
        self._get_session_path = get_session_path
        self._list_sessions = list_sessions
        self._load_plan_state = load_plan_state
        self._load_session_metadata = load_session_metadata
        self._load_session_history = load_session_history
        self._save_plan_state = save_plan_state
        self._save_session_metadata = save_session_metadata
        self._save_session_history = save_session_history
        self.current_name = default_name

    def _validate(self, name: str) -> str:
        self._get_session_path(name)
        return name

    def list(self) -> list[dict[str, Any]]:
        names = sorted(set(self._list_sessions()) | {self.current_name})
        summaries = []
        for name in names:
            metadata = self._load_session_metadata(name)
            title = str(metadata.get("title") or "").strip()
            summaries.append({
                "name": name,
                "title": title,
                "current": name == self.current_name,
                "source": self.source,
            })
        return summaries

    def load(self, name: str):
        return self._load_session_history(self._validate(name))

    def save(self, name: str, messages: list[Any]) -> None:
        self._save_session_history(self._validate(name), messages)

    def load_plan(self, name: str) -> dict[str, Any] | None:
        return self._load_plan_state(self._validate(name))

    def save_plan(self, name: str, plan_json: str, phase: str) -> None:
        self._save_plan_state(self._validate(name), plan_json, phase)

    def clear_plan(self, name: str) -> None:
        self._clear_plan_state(self._validate(name))

    def create(self, name: str) -> list[Any]:
        self.save(self._validate(name), [])
        return []

    def title(self, name: str) -> str:
        metadata = self._load_session_metadata(self._validate(name))
        return str(metadata.get("title") or "").strip()

    def set_title(self, name: str, title: str) -> None:
        clean_title = title.strip()
        if clean_title:
            self._save_session_metadata(self._validate(name), {"title": clean_title})

    def delete(self, name: str) -> str:
        session_name = self._validate(name)
        session_path = self._get_session_path(session_name)
        if not session_path.exists():
            raise ValueError(f"Session not found: {name}")

        remaining = sorted(n for n in self._list_sessions() if n != session_name)
        session_path.unlink()
        if self.current_name == session_name:
            next_name = remaining[0] if remaining else "default"
            if not self._get_session_path(next_name).exists():
                self.save(next_name, [])
            self.current_name = next_name
        return self.current_name

    def rename(self, old_name: str, new_name: str) -> None:
        old_path = self._get_session_path(self._validate(old_name))
        new_path = self._get_session_path(self._validate(new_name))
        if not old_path.exists():
            raise ValueError(f"Session not found: {old_name}")
        if new_path.exists():
            raise ValueError(f"Session already exists: {new_name}")
        old_path.rename(new_path)
        if self.current_name == old_name:
            self.current_name = new_name

    def export(self, name: str, fmt: str) -> dict[str, Any]:
        session_name = self._validate(name)
        messages = self._load_session_history(session_name)
        fmt = fmt.lower()
        if fmt not in {"markdown", "md", "json"}:
            raise ValueError("Export format must be markdown or json.")
        if fmt == "json":
            data = [_message_to_json(m) for m in messages]
            content = json.dumps(data, ensure_ascii=False, indent=2)
            fmt = "json"
        else:
            parts = [f"# Theseus session: {session_name}", ""]
            for msg in messages:
                parts.append(f"## {getattr(msg, 'role', 'message')}")
                parts.append("")
                parts.append(_message_text(msg) or "")
                parts.append("")
            content = "\n".join(parts).rstrip() + "\n"
            fmt = "markdown"
        return {"name": session_name, "format": fmt, "content": content, "source": self.source}


def _message_text(message: Any) -> str:
    text = getattr(message, "text", "")
    if text:
        return str(text)
    blocks = getattr(message, "content", []) or []
    chunks: list[str] = []
    for block in blocks:
        block_text = getattr(block, "text", None)
        if block_text is not None:
            chunks.append(str(block_text))
        elif getattr(block, "type", "") == "tool_result":
            chunks.append(str(getattr(block, "content", "")))
    return "\n".join(c for c in chunks if c)


def _message_to_json(message: Any) -> dict[str, Any]:
    if hasattr(message, "model_dump"):
        return message.model_dump()
    if hasattr(message, "dict"):
        return message.dict()
    return {"role": getattr(message, "role", "message"), "text": _message_text(message)}


def history_for_ui(messages: list[Any]) -> list[dict[str, str]]:
    history: list[dict[str, str]] = []
    for msg in messages:
        role = str(getattr(msg, "role", "message"))
        text = _message_text(msg)
        if text:
            history.append({"type": "message", "role": role, "text": text})
    return history


def _json_safe(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return _json_safe(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]
    if isinstance(value, Path):
        return str(value)
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def event_to_json(event: Any) -> dict[str, Any]:
    if dataclasses.is_dataclass(event):
        payload = dataclasses.asdict(event)
    else:
        payload = {"value": str(event)}
    return {"type": type(event).__name__, **_json_safe(payload)}


def _phase_value(phase: Any) -> str:
    return str(getattr(phase, "value", phase or ""))


def _registry_tool_names(registry: Any) -> list[str]:
    if registry is None:
        return []
    try:
        return sorted(tool.name for tool in registry.list_tools())
    except Exception:
        pass
    try:
        tools = getattr(registry, "_tools", {})
        return sorted(str(name) for name in tools.keys())
    except Exception:
        return []


class EditorRuntime:
    def __init__(
        self,
        *,
        model: str,
        user_level: int,
        cwd: Path,
        permission_prompt: Optional[Callable[[str, str], Any]] = None,
    ) -> None:
        self.model = model
        self.user_level = user_level
        self.cwd = cwd
        self.permission_prompt = permission_prompt or self._default_permission_prompt
        self.sessions = LocalSessionProvider()
        self.sm: Any = None
        self.engine: Any = None
        self.full_registry: Any = None
        self.tool_permissions: dict[str, int] = dict(DEFAULT_TOOL_PERMISSIONS)
        self.AgentMode: Any = None
        self.PlanPhase: Any = None
        self.initialized = False

    async def _default_permission_prompt(self, tool_name: str, prompt_msg: str) -> bool:
        return True

    async def initialize(self) -> list[dict[str, Any]]:
        if self.initialized:
            return []
        from theseus_engine.core.engine_builder import setup_engine
        from theseus_engine.models.state import AgentMode, PlanPhase, TheseusStateMachine
        from theseus_engine.wrappers.llm_clients.theseus_client import TheseusLLMClient

        self.AgentMode = AgentMode
        self.PlanPhase = PlanPhase
        self.sm = TheseusStateMachine(initial_mode=AgentMode.AGENT)
        os.environ["THESEUS_MODEL"] = self.model
        os.environ["OPENHARNESS_MODEL"] = self.model
        client = TheseusLLMClient(self.model)
        with contextlib.redirect_stdout(sys.stderr):
            self.engine, self.full_registry = await setup_engine(
                self.sm,
                self.user_level,
                self.tool_permissions,
                self.permission_prompt,
                api_client=client,
                reset_stats=True,
                cwd=self.cwd,
            )
        initial_messages = self.sessions.load(self.sessions.current_name)
        if initial_messages:
            self.engine.load_messages(initial_messages)
        self._restore_plan_state(self.sessions.load_plan(self.sessions.current_name))
        self.initialized = True
        return [
            {
                "type": "RunnerReady",
                "mode": "json",
                "model": self.model,
                "cwd": str(self.cwd),
                "session": self.sessions.current_name,
            },
            {
                "type": "SessionListEvent",
                "source": self.sessions.source,
                "current": self.sessions.current_name,
                "sessions": self.sessions.list(),
            },
            {
                "type": "SessionChangedEvent",
                "source": self.sessions.source,
                "current": self.sessions.current_name,
                "history": history_for_ui(initial_messages),
                "planState": self._current_plan_state_for_ui(),
            },
        ]

    def set_mode(self, mode: str, *, announce: bool = True) -> list[dict[str, Any]]:
        normalized = mode.strip().lower()
        mode_map = {
            "agent": ("Agent", self.AgentMode.AGENT),
            "ask": ("Ask", self.AgentMode.ASK),
            "plan": ("Plan", self.AgentMode.PLAN),
        }
        if normalized not in mode_map:
            return [{"type": "StatusEvent", "message": f"지원하지 않는 모드입니다: {mode}"}]
        label, mode_val = mode_map[normalized]
        if self.sm.mode != mode_val:
            self.sm.switch_mode(mode_val)
        self._refresh_active_tool_registry()
        self._set_engine_system_prompt()
        self.engine.set_plan_drafting(getattr(self.sm, "is_plan_drafting", False))
        if not announce:
            return []
        return [{"type": "StatusEvent", "message": f"✅ {label} 모드로 전환됐습니다."}]

    def _refresh_active_tool_registry(self) -> None:
        """Synchronize the active tool schema with the current mode/PLAN phase."""
        if self.engine is None or self.full_registry is None or self.sm is None:
            return
        can_create_tool = (
            self.sm.mode == self.AgentMode.PLAN
            and self.sm.plan_phase == self.PlanPhase.EXECUTING
        )
        exclude = set() if can_create_tool else {"create_tool"}
        active_registry = self.full_registry.__class__()
        for tool in self.full_registry.list_tools():
            if tool.name in exclude:
                continue
            required = self.tool_permissions.get(
                tool.name,
                getattr(tool, "permission_level", 1),
            )
            if self.user_level >= required:
                active_registry.register(tool)
        if hasattr(self.engine, "set_tool_registry"):
            self.engine.set_tool_registry(active_registry)
        else:
            self.engine._tool_registry = active_registry
            self.engine.tool_metadata["active_registry"] = active_registry

    def _active_tool_names(self) -> tuple[str, ...]:
        """Return the engine's current active tool names for prompt capability gating."""
        registry = None
        if self.engine is not None:
            metadata = getattr(self.engine, "tool_metadata", None)
            if isinstance(metadata, dict):
                registry = metadata.get("active_registry")
            if registry is None:
                registry = getattr(self.engine, "_tool_registry", None)
        if registry is None:
            registry = self.full_registry
        if registry is None or not hasattr(registry, "list_tools"):
            return ()
        return tuple(tool.name for tool in registry.list_tools())

    def _set_engine_system_prompt(self) -> None:
        """Refresh system prompt and mode metadata from the current state machine."""
        if self.engine is None or self.sm is None:
            return
        metadata = getattr(self.engine, "tool_metadata", None)
        if isinstance(metadata, dict):
            metadata["agent_mode"] = self.sm.mode.value
        self.engine.set_system_prompt(
            self.sm.get_system_prompt(available_tools=self._active_tool_names())
        )

    def _plan_phase_from_text(self, phase: str | None) -> Any:
        normalized = str(phase or "").strip().lower()
        phase_map = {
            "draft": self.PlanPhase.DRAFTING,
            "drafting": self.PlanPhase.DRAFTING,
            "wait": self.PlanPhase.WAIT_FOR_REVIEW,
            "review": self.PlanPhase.WAIT_FOR_REVIEW,
            "waitforreview": self.PlanPhase.WAIT_FOR_REVIEW,
            "wait_for_review": self.PlanPhase.WAIT_FOR_REVIEW,
            "executing": self.PlanPhase.EXECUTING,
            "execute": self.PlanPhase.EXECUTING,
            "verifying": self.PlanPhase.VERIFYING,
            "verify": self.PlanPhase.VERIFYING,
        }
        return phase_map.get(normalized, self.PlanPhase.DRAFTING)

    def _current_plan_state(self) -> dict[str, Any] | None:
        if self.sm is None or self.sm.mode != self.AgentMode.PLAN or not self.sm.plan:
            return None
        phase = getattr(getattr(self.sm, "plan_phase", None), "value", "Drafting")
        return {
            "plan_json": self.sm.plan,
            "phase": phase,
            **plan_task_counts(self.sm.plan),
        }

    def _current_plan_state_for_ui(self) -> dict[str, Any] | None:
        state = self._current_plan_state()
        if not state:
            return None
        try:
            state["structured_plan"] = json.loads(str(state.get("plan_json") or "{}"))
        except json.JSONDecodeError:
            pass
        return state

    def _save_current_session(self) -> None:
        self.sessions.save(self.sessions.current_name, self.engine.messages)
        plan_state = self._current_plan_state()
        if plan_state:
            self.sessions.save_plan(
                self.sessions.current_name,
                str(plan_state.get("plan_json") or ""),
                str(plan_state.get("phase") or "Drafting"),
            )
        else:
            self.sessions.clear_plan(self.sessions.current_name)

    def _maybe_title_current_session(self, prompt: str) -> list[dict[str, Any]]:
        if self.engine.messages or self.sessions.title(self.sessions.current_name):
            return []
        title = derive_session_title(prompt)
        if not title:
            return []
        self.sessions.set_title(self.sessions.current_name, title)
        return [{
            "type": "SessionListEvent",
            "source": self.sessions.source,
            "current": self.sessions.current_name,
            "sessions": self.sessions.list(),
        }]

    def _restore_plan_state(self, plan_state: dict[str, Any] | None) -> None:
        if not plan_state or not plan_state.get("plan_json"):
            if self.sm.mode == self.AgentMode.PLAN:
                self.sm.plan = ""
                self.sm.set_plan_phase(self.PlanPhase.DRAFTING)
            self._refresh_active_tool_registry()
            self._set_engine_system_prompt()
            self.engine.set_plan_drafting(getattr(self.sm, "is_plan_drafting", False))
            return
        if self.sm.mode != self.AgentMode.PLAN:
            self.sm.switch_mode(self.AgentMode.PLAN)
        self.sm.plan = str(plan_state.get("plan_json") or "")
        self.sm.set_plan_phase(self._plan_phase_from_text(str(plan_state.get("phase") or "")))
        self._refresh_active_tool_registry()
        self._set_engine_system_prompt()
        self.engine.set_plan_drafting(getattr(self.sm, "is_plan_drafting", False))

    def _clear_plan_runtime(self) -> None:
        if self.sm.mode == self.AgentMode.PLAN:
            self.sm.plan = ""
            self.sm.set_plan_phase(self.PlanPhase.DRAFTING)
        else:
            self.sm.plan = ""
        self._refresh_active_tool_registry()
        self._set_engine_system_prompt()
        self.engine.set_plan_drafting(getattr(self.sm, "is_plan_drafting", False))

    def handle_internal_command(self, payload: dict[str, Any]) -> list[dict[str, Any]] | None:
        if payload.get("type") != "setMode":
            return None
        mode = payload.get("mode")
        if not isinstance(mode, str):
            return [{"type": "StatusEvent", "message": "모드 전환 요청이 올바르지 않습니다."}]
        return self.set_mode(mode)

    def handle_slash_command(self, cmd: str) -> list[dict[str, Any]] | None:
        raw = cmd.strip()
        c = raw.lower()
        events: list[dict[str, Any]] = []
        if c in {"/agent", "/ask", "/plan", "/coordinator"}:
            return [{"type": "StatusEvent", "message": "모드 전환은 입력창 아래 모드 선택을 사용하세요."}]
        if c == "/clear":
            return [{"type": "ClearChat"}]
        if c in ("/tools", "/tools custom"):
            tool_names = _registry_tool_names(self.full_registry)
            if not tool_names:
                return [{"type": "StatusEvent", "message": "⚠️ 등록된 도구가 없습니다."}]
            if c == "/tools custom":
                custom = [t for t in tool_names if t not in DEFAULT_TOOL_PERMISSIONS]
                msg = "🔧 커스텀 도구 목록:\n" + "\n".join(f"  • {t}" for t in custom) if custom else "커스텀 도구가 없습니다. custom_tools/ 폴더에 .py 파일을 추가하세요."
            else:
                msg = f"🛠 사용 가능한 도구 ({len(tool_names)}개):\n" + "\n".join(f"  • {t}" for t in tool_names)
            return [{"type": "StatusEvent", "message": msg}]
        if c in ("/stats", "/cost"):
            try:
                from theseus_engine.observability.stats import SessionStats

                s = SessionStats.get()
                msg = (
                    f"📊 세션 통계\n"
                    f"  입력 토큰: {getattr(s, 'input_tokens', 0):,}\n"
                    f"  출력 토큰: {getattr(s, 'output_tokens', 0):,}\n"
                    f"  총 비용:   ${getattr(s, 'total_cost_usd', 0.0):.4f}"
                )
            except Exception as e:
                msg = f"통계를 가져올 수 없습니다: {e}"
            return [{"type": "StatusEvent", "message": msg}]
        if c.startswith("/session"):
            return self._handle_session_command(raw)
        if c in ("/plan approve", "/plan accept"):
            return self._apply_plan_review("approve")
        if c in ("/plan reject", "/plan deny"):
            return self._apply_plan_review("reject")
        if c in ("/plan cancel", "/plan clear"):
            return self._apply_plan_review("cancel")
        if c in ("/plan delete", "/plan remove"):
            return self._apply_plan_review("delete")
        if c == "/validate":
            try:
                from theseus_engine.tools.core import load_custom_tools
                from theseus_engine.tools.core.base_tools import ToolRegistry

                registry = ToolRegistry()
                with contextlib.redirect_stdout(sys.stderr):
                    tools = load_custom_tools(registry, dict(DEFAULT_TOOL_PERMISSIONS))
                msg = f"✅ 유효성 검사 통과 ({len(tools)}개 도구)"
            except Exception as e:
                msg = f"검사 오류: {e}"
            return [{"type": "StatusEvent", "message": msg}]
        if c in ("/help", "/?"):
            return [{
                "type": "StatusEvent",
                "message": (
                    "📖 사용 가능한 명령어:\n"
                    "  /tools         — 전체 도구 목록\n"
                    "  /tools custom  — 커스텀 도구 목록\n"
                    "  /stats         — 토큰/비용 통계\n"
                    "  /validate      — 커스텀 도구 유효성 검사\n"
                    "  /session list  — 세션 목록\n"
                    "  /session new   — 새 세션 시작\n"
                    "  /session delete <name> — 세션 삭제\n"
                    "  /plan cancel   — 진행 중인 PLAN 취소\n"
                    "  /plan delete   — 현재 세션 PLAN 삭제\n"
                    "  /clear         — 채팅 히스토리 초기화\n"
                    "  /quit, /exit   — 에이전트 종료"
                ),
            }]
        return None

    def _apply_plan_review(self, action: str) -> list[dict[str, Any]]:
        counts = plan_task_counts(getattr(self.sm, "plan", ""))
        if action in {"cancel", "delete"}:
            event_action = "deleted" if action == "delete" else "cancelled"
            self._clear_plan_runtime()
            self.sessions.clear_plan(self.sessions.current_name)
            return [
                {
                    "type": "PlanReviewEvent",
                    "source": "local",
                    "action": event_action,
                    "phase": getattr(getattr(self.sm, "plan_phase", None), "value", ""),
                    **counts,
                },
                {"type": "StatusEvent", "message": "PLAN이 삭제되었습니다." if action == "delete" else "PLAN이 취소되었습니다."},
            ]

        if self.sm.mode != self.AgentMode.PLAN or self.sm.plan_phase != self.PlanPhase.WAIT_FOR_REVIEW:
            return [
                {
                    "type": "PlanReviewEvent",
                    "source": "local",
                    "action": "not_reviewable",
                    "phase": getattr(getattr(self.sm, "plan_phase", None), "value", ""),
                    "message": "현재 검토 대기 중인 PLAN이 없습니다.",
                    **counts,
                }
            ]

        if action == "approve":
            self.sm.set_plan_phase(self.PlanPhase.EXECUTING)
            self._refresh_active_tool_registry()
            self._set_engine_system_prompt()
            self.engine.set_plan_drafting(False)
            self._save_current_session()
            return [
                {
                    "type": "PlanReviewEvent",
                    "source": "local",
                    "action": "approved",
                    "phase": self.sm.plan_phase.value,
                    **counts,
                },
                {"type": "StatusEvent", "message": "PLAN 승인됨. 실행을 바로 시작합니다."},
            ]

        self.sm.set_plan_phase(self.PlanPhase.DRAFTING)
        self.sm.plan = ""
        self._refresh_active_tool_registry()
        self._set_engine_system_prompt()
        self.engine.set_plan_drafting(True)
        self.sessions.clear_plan(self.sessions.current_name)
        return [
            {
                "type": "PlanReviewEvent",
                "source": "local",
                "action": "rejected",
                "phase": self.sm.plan_phase.value,
                **counts,
            },
            {"type": "StatusEvent", "message": "PLAN 거부됨. 피드백을 입력하면 다시 초안을 작성합니다."},
        ]

    def _handle_session_command(self, raw: str) -> list[dict[str, Any]]:
        try:
            parts = shlex.split(raw)
        except ValueError as exc:
            return [{"type": "StatusEvent", "message": f"세션 명령 파싱 오류: {exc}"}]
        action = parts[1].lower() if len(parts) > 1 else "list"
        events: list[dict[str, Any]] = []
        try:
            if action == "list":
                events.append({"type": "SessionListEvent", "source": self.sessions.source, "current": self.sessions.current_name, "sessions": self.sessions.list()})
                names = ", ".join(s["name"] for s in self.sessions.list())
                events.append({"type": "StatusEvent", "message": f"세션 목록: {names}"})
            elif action == "new" and len(parts) >= 3:
                self._save_current_session()
                new_name = parts[2]
                self.sessions.create(new_name)
                self.sessions.current_name = new_name
                self.engine.clear()
                self._clear_plan_runtime()
                self.sessions.clear_plan(new_name)
                events.extend(self._session_changed_events(new_name, []))
                events.append({"type": "StatusEvent", "message": f"새 세션으로 전환: {new_name}"})
            elif action == "switch" and len(parts) >= 3:
                self._save_current_session()
                next_name = parts[2]
                messages = self.sessions.load(next_name)
                self.sessions.current_name = next_name
                self.engine.load_messages(messages)
                self._restore_plan_state(self.sessions.load_plan(next_name))
                events.extend(self._session_changed_events(next_name, history_for_ui(messages)))
                events.append({"type": "StatusEvent", "message": f"세션 전환: {next_name}"})
            elif action in {"delete", "remove"} and len(parts) >= 3:
                target_name = parts[2]
                was_current = target_name == self.sessions.current_name
                next_name = self.sessions.delete(target_name)
                if was_current:
                    messages = self.sessions.load(next_name)
                    self.engine.load_messages(messages)
                    self._restore_plan_state(self.sessions.load_plan(next_name))
                    events.extend(self._session_changed_events(next_name, history_for_ui(messages)))
                else:
                    events.append({"type": "SessionListEvent", "source": self.sessions.source, "current": self.sessions.current_name, "sessions": self.sessions.list()})
                events.append({"type": "StatusEvent", "message": f"세션 삭제: {target_name}"})
            elif action == "rename" and len(parts) >= 4:
                old_name, new_name = parts[2], parts[3]
                if old_name == self.sessions.current_name:
                    self._save_current_session()
                self.sessions.rename(old_name, new_name)
                events.extend(self._session_changed_events(self.sessions.current_name, history_for_ui(self.engine.messages)))
                events.append({"type": "StatusEvent", "message": f"세션 이름 변경: {old_name} → {new_name}"})
            elif action == "export" and len(parts) >= 4:
                if parts[2] == self.sessions.current_name:
                    self._save_current_session()
                exported = self.sessions.export(parts[2], parts[3])
                events.append({"type": "SessionExportedEvent", **exported})
                events.append({"type": "StatusEvent", "message": f"세션 내보내기 완료: {parts[2]} ({exported['format']})"})
            else:
                events.append({"type": "StatusEvent", "message": "사용법: /session list | /session new <name> | /session switch <name> | /session delete <name> | /session rename <old> <new> | /session export <name> markdown|json"})
        except Exception as exc:
            events.append({"type": "StatusEvent", "message": f"세션 명령 실패: {exc}"})
        return events

    def _session_changed_events(self, current: str, history: list[dict[str, str]]) -> list[dict[str, Any]]:
        return [
            {
                "type": "SessionChangedEvent",
                "source": self.sessions.source,
                "current": current,
                "history": history,
                "planState": self._current_plan_state_for_ui(),
            },
            {"type": "SessionListEvent", "source": self.sessions.source, "current": self.sessions.current_name, "sessions": self.sessions.list()},
        ]

    async def submit(self, prompt: str):
        await self.initialize()
        prompt = prompt.lstrip("\ufeff").strip()
        if not prompt:
            return
        if prompt.startswith("{"):
            try:
                internal_payload = json.loads(prompt)
            except json.JSONDecodeError:
                internal_payload = None
            if isinstance(internal_payload, dict):
                handled = self.handle_internal_command(internal_payload)
                if handled is not None:
                    for event in handled:
                        yield event
                    return
        raw_lower = prompt.strip("\"'").lower()
        if raw_lower in {"exit", "quit", "/quit", "/exit"}:
            self._save_current_session()
            yield {"type": "RunnerStopped"}
            return
        if prompt.startswith("/") and raw_lower in {"/plan approve", "/plan accept"}:
            approved = False
            for event in self._apply_plan_review("approve"):
                if event.get("type") == "PlanReviewEvent" and event.get("action") == "approved":
                    approved = True
                yield event
            if not approved:
                return
            prompt = PLAN_CONTINUE_PROMPT
        elif prompt.startswith("/"):
            handled = self.handle_slash_command(prompt)
            if handled is not None:
                for event in handled:
                    yield event
                return
            yield {"type": "StatusEvent", "message": f"알 수 없는 명령어: {prompt}\n'/help'로 명령어 목록을 확인하세요."}
            return

        review_action = classify_plan_review_response(prompt)
        if (
            review_action
            and self.sm.mode == self.AgentMode.PLAN
            and self.sm.plan_phase == self.PlanPhase.WAIT_FOR_REVIEW
        ):
            approved = False
            for event in self._apply_plan_review(review_action):
                if event.get("type") == "PlanReviewEvent" and event.get("action") == "approved":
                    approved = True
                yield event
            if approved:
                prompt = PLAN_CONTINUE_PROMPT
            else:
                return

        if prompt not in {PLAN_CONTINUE_PROMPT, PLAN_VERIFICATION_PROMPT, PLAN_TOOL_ERROR_PROMPT}:
            for event in self._maybe_title_current_session(prompt):
                yield event

        max_auto_resume = 5
        auto_resume_count = 0
        current_prompt = prompt

        try:
            while True:
                accumulated_text = ""
                tool_called = False
                tool_error = False
                plan_drafted = False
                transitioned_to_verifying = False
                verification_complete = False

                self.engine.set_plan_drafting(
                    getattr(self.sm, "is_plan_drafting", False)
                )
                self._refresh_active_tool_registry()
                self._set_engine_system_prompt()

                with contextlib.redirect_stdout(sys.stderr):
                    async for event in self.engine.submit_message(current_prompt):
                        event_name = type(event).__name__
                        if event_name == "AssistantTextDelta":
                            accumulated_text += str(getattr(event, "text", ""))
                        elif event_name == "ToolExecutionStarted":
                            tool_called = True
                        elif event_name == "ToolExecutionCompleted":
                            if bool(getattr(event, "is_error", False)):
                                tool_error = True
                        elif event_name == "PlanDraftedEvent":
                            plan_drafted = True
                            self.sm.plan = json.dumps(
                                getattr(event, "structured_plan", {}),
                                ensure_ascii=False,
                                indent=2,
                            )
                            self.sm.set_plan_phase(self.PlanPhase.WAIT_FOR_REVIEW)
                            self._refresh_active_tool_registry()
                            self._set_engine_system_prompt()
                            self.engine.set_plan_drafting(False)
                            self._save_current_session()
                        yield event_to_json(event)

                if self.sm.mode == self.AgentMode.PLAN and not plan_drafted:
                    if (
                        self.sm.plan_phase == self.PlanPhase.EXECUTING
                        and contains_execution_complete(accumulated_text)
                    ):
                        from_phase = _phase_value(self.sm.plan_phase)
                        self.sm.set_plan_phase(self.PlanPhase.VERIFYING)
                        self._refresh_active_tool_registry()
                        self._set_engine_system_prompt()
                        self._save_current_session()
                        transitioned_to_verifying = True
                        yield event_to_json(
                            PlanPhaseTransitionRequested(
                                from_phase=from_phase,
                                to_phase=_phase_value(self.sm.plan_phase),
                                reason="Assistant signaled PLAN execution completion.",
                                trigger="execution_complete_marker",
                            )
                        )
                        yield {
                            "type": "StatusEvent",
                            "message": "실행 완료 — 자동 검증을 시작합니다.",
                        }
                    elif (
                        self.sm.plan_phase == self.PlanPhase.VERIFYING
                        and contains_verification_complete(accumulated_text)
                    ):
                        verification_complete = True
                        from_phase = _phase_value(self.sm.plan_phase)
                        counts = plan_task_counts(getattr(self.sm, "plan", ""))
                        yield event_to_json(
                            PlanPhaseTransitionRequested(
                                from_phase=from_phase,
                                to_phase="Completed",
                                reason="Assistant signaled PLAN verification completion.",
                                trigger="verification_complete_marker",
                            )
                        )
                        yield {
                            "type": "PlanReviewEvent",
                            "source": "local",
                            "action": "completed",
                            "phase": self.sm.plan_phase.value,
                            **counts,
                        }
                        yield {
                            "type": "StatusEvent",
                            "message": "PLAN 검증 완료.",
                        }
                        self._clear_plan_runtime()
                        self.sessions.clear_plan(self.sessions.current_name)

                should_resume = False
                resume_prompt = PLAN_CONTINUE_PROMPT
                if self.sm.mode == self.AgentMode.PLAN:
                    if transitioned_to_verifying:
                        should_resume = True
                        resume_prompt = PLAN_VERIFICATION_PROMPT
                    elif verification_complete:
                        should_resume = False
                    elif self.sm.plan_phase in (
                        self.PlanPhase.EXECUTING,
                        self.PlanPhase.VERIFYING,
                    ):
                        if tool_error:
                            should_resume = True
                            resume_prompt = PLAN_TOOL_ERROR_PROMPT
                        elif not tool_called:
                            should_resume = True
                if should_resume and auto_resume_count < max_auto_resume:
                    auto_resume_count += 1
                    current_prompt = resume_prompt
                    continue
                break
            self._save_current_session()
        except Exception as exc:
            yield event_to_json(ErrorEvent(message=str(exc), recoverable=True, error_type="unknown"))
