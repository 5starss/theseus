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
    actor_role: str = "ADMIN"  # "ADMIN" | "MEMBER" — standalone은 기본 ADMIN
    project_tool_permissions: dict = field(default_factory=dict)
    ask_permission: Any = None
    full_registry: Any = None  # 전체 ToolRegistry (커스텀 툴 조회 등에 사용)

    # 루프 제어 플래그
    pending_mode_reminders: tuple[str, ...] = ()
    waiting_for_user: bool = False

    # 자동 재개 카운터 (턴 단위 — WAIT_FOR_REVIEW 강등 시 리셋)
    auto_resume_count: int = 0
    last_error_sig: str = ""
    repeated_error_count: int = 0

    # 세션 전체 누적 강등 카운터 (리셋 안 됨 — 무한루프 세션 차단용)
    session_resume_total: int = 0

    # 상수
    MAX_AUTO_RESUME: int = 5
    MAX_REPEATED_ERRORS: int = 2
    MAX_SESSION_RESUMES: int = 20  # 세션 전체 자동 재개 절대 상한
