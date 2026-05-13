import asyncio
import json
from pathlib import Path
from typing import List
from theseus_engine.models.messages import ConversationMessage

# Session History Management
SESSION_DIR = Path(".theseus_sessions")
SESSION_DIR.mkdir(exist_ok=True)


def get_session_path(session_name: str) -> Path:
    """Get the file path for a given session name."""
    if not session_name or not session_name.isalnum():
        raise ValueError("Session name must be alphanumeric.")
    return SESSION_DIR / f"{session_name}.json"


def list_sessions() -> List[str]:
    """List all available session names."""
    return [p.stem for p in SESSION_DIR.glob("*.json")]


def load_session_metadata(session_name: str) -> dict:
    """Load display metadata for a session."""
    session_file = get_session_path(session_name)
    envelope = _read_envelope(session_file)
    metadata = envelope.get("metadata", {}) if isinstance(envelope, dict) else {}
    if not isinstance(metadata, dict):
        metadata = {}
    title = envelope.get("title") if isinstance(envelope, dict) else None
    if isinstance(title, str) and title.strip() and not metadata.get("title"):
        metadata["title"] = title.strip()
    return metadata


def save_session_metadata(session_name: str, metadata: dict) -> None:
    """Merge display metadata into the session envelope."""
    session_file = get_session_path(session_name)
    try:
        envelope = _read_envelope(session_file)
        if not envelope:
            envelope = {"history": []}
        existing = envelope.get("metadata", {})
        if not isinstance(existing, dict):
            existing = {}
        existing.update(metadata)
        envelope["metadata"] = existing
        if "title" in metadata:
            envelope["title"] = metadata["title"]
        _write_envelope(session_file, envelope)
    except Exception as e:
        print(f"⚠️ Failed to save session metadata for '{session_name}': {e}")


def _serialize_messages(messages: List[ConversationMessage]) -> list:
    """ConversationMessage 리스트를 JSON 직렬화 가능한 dict 리스트로 변환합니다."""
    msg_data = []
    for msg in messages:
        msg_dict = {"role": msg.role, "content": []}
        for block in msg.content:
            if hasattr(block, "model_dump"):
                msg_dict["content"].append(block.model_dump())
            elif hasattr(block, "dict"):
                msg_dict["content"].append(block.dict())
            else:
                msg_dict["content"].append(block)
        if hasattr(msg, "_raw_tool_calls"):
            msg_dict["_raw_tool_calls"] = getattr(msg, "_raw_tool_calls")
        msg_data.append(msg_dict)
    return msg_data


def _read_envelope(session_file: Path) -> dict:
    """세션 파일을 읽어 envelope dict를 반환합니다. 파일 없으면 빈 dict."""
    if not session_file.exists():
        return {}
    try:
        existing = json.loads(session_file.read_text(encoding="utf-8"))
        return existing if isinstance(existing, dict) else {}
    except Exception:
        return {}


def _write_envelope(session_file: Path, envelope: dict) -> None:
    """envelope dict를 세션 파일에 씁니다."""
    session_file.write_text(
        json.dumps(envelope, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def save_session_history(
    session_name: str,
    messages: List[ConversationMessage],
    plan_state: dict | None = None,
) -> None:
    """대화 히스토리와 선택적 plan_state를 세션 파일에 저장합니다.

    동기 컨텍스트에서 직접 호출 가능합니다.
    async 컨텍스트에서는 save_session_history_async를 사용하세요.
    """
    session_file = get_session_path(session_name)
    try:
        envelope = _read_envelope(session_file)
        envelope["history"] = _serialize_messages(messages)
        if plan_state is not None:
            envelope["plan_state"] = plan_state
        _write_envelope(session_file, envelope)
    except Exception as e:
        print(f"⚠️ Failed to save session history for '{session_name}': {e}")


async def save_session_history_async(
    session_name: str,
    messages: List[ConversationMessage],
    plan_state: dict | None = None,
) -> None:
    """대화 히스토리와 선택적 plan_state를 세션 파일에 비동기로 저장합니다.

    async 루프 블로킹 없이 파일 I/O를 수행합니다.
    """
    session_file = get_session_path(session_name)
    try:
        envelope = await asyncio.to_thread(_read_envelope, session_file)
        envelope["history"] = _serialize_messages(messages)
        if plan_state is not None:
            envelope["plan_state"] = plan_state
        await asyncio.to_thread(_write_envelope, session_file, envelope)
    except Exception as e:
        print(f"⚠️ Failed to save session history for '{session_name}': {e}")


def load_session_history(session_name: str) -> List[ConversationMessage]:
    """세션 파일에서 대화 히스토리를 로드합니다.

    Returns:
        대화 메시지 리스트. plan_state가 필요하면 load_plan_state를 별도 호출하세요.
    """
    session_file = get_session_path(session_name)
    if not session_file.exists():
        return []
    try:
        raw = json.loads(session_file.read_text(encoding="utf-8"))

        # 하위 호환: 기존 flat-list 형식도 지원
        msg_list = raw if isinstance(raw, list) else raw.get("history", [])

        messages = []
        for msg_dict in msg_list:
            role = msg_dict.get("role", "user")
            content = msg_dict.get("content", [])
            msg = ConversationMessage(role=role, content=content)
            if "_raw_tool_calls" in msg_dict:
                object.__setattr__(
                    msg, "_raw_tool_calls", msg_dict["_raw_tool_calls"]
                )
            messages.append(msg)
        return messages
    except Exception as e:
        print(f"⚠️ Failed to load session history for '{session_name}': {e}")
        return []


# ── Plan State Persistence ──────────────────────────────────────


def save_plan_state(
    session_name: str,
    plan_json: str,
    phase: str,
    completed_tasks: list[str] | None = None,
    last_error: str | None = None,
) -> None:
    """Plan 실행 상태를 세션 파일에 저장합니다."""
    session_file = get_session_path(session_name)
    try:
        raw = session_file.read_text(encoding="utf-8") if session_file.exists() else None
        if raw:
            envelope = json.loads(raw)
            if isinstance(envelope, list):
                envelope = {"history": envelope}
        else:
            envelope = {"history": []}

        envelope["plan_state"] = {
            "plan_json": plan_json,
            "phase": phase,
            "completed_tasks": completed_tasks or [],
            "last_error": last_error,
        }
        _write_envelope(session_file, envelope)
    except Exception as e:
        print(f"⚠️ Failed to save plan state for '{session_name}': {e}")


def load_plan_state(session_name: str) -> dict | None:
    """세션 파일에서 Plan 상태를 로드합니다.

    Returns:
        {"plan_json": ..., "phase": ..., "completed_tasks": [...],
        "last_error": ...} 또는 None.
    """
    session_file = get_session_path(session_name)
    if not session_file.exists():
        return None
    try:
        raw = json.loads(session_file.read_text(encoding="utf-8"))
        return raw.get("plan_state") if isinstance(raw, dict) else None
    except Exception:
        return None


def clear_plan_state(session_name: str) -> None:
    """세션에서 Plan 상태를 제거합니다 (계획 완료 시 호출)."""
    session_file = get_session_path(session_name)
    if not session_file.exists():
        return
    try:
        raw = json.loads(session_file.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and "plan_state" in raw:
            del raw["plan_state"]
            _write_envelope(session_file, raw)
    except Exception:
        pass
