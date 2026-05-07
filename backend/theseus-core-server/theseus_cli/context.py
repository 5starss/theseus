"""CLI 실행 컨텍스트 — 가변 상태를 단일 객체로 묶어 모듈 간 전달을 단순화합니다."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from theseus_engine.models.state import TheseusStateMachine
    from theseus_engine.wrappers.llm_clients.theseus_client import TheseusLLMClient


@dataclass
class CLIContext:
    sm: "TheseusStateMachine"
    engine: Any
    client: "TheseusLLMClient"
    user_level: int
    project_tool_permissions: dict
    ask_permission: Any

    # 루프 제어 플래그
    pending_mode_notification: str = ""
    waiting_for_user: bool = False

    # 자동 재개 카운터
    auto_resume_count: int = 0
    last_error_sig: str = ""
    repeated_error_count: int = 0

    # 상수
    MAX_AUTO_RESUME: int = 5
    MAX_REPEATED_ERRORS: int = 2
