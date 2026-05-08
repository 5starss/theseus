"""Theseus 런타임 모드 감지 — Standalone vs Server.

Standalone (CLI/TUI):
  - 로컬 파일시스템 기반 (.meta.json, custom_tools/)
  - HITL 프롬프트 직접 표시

Server (FastAPI SSE):
  - Spring Backend + DB 기반
  - JWT 인증, project_id/user_id 컨텍스트
"""

from __future__ import annotations

import os
from enum import Enum


class RuntimeMode(str, Enum):
    """Theseus 에이전트 실행 환경."""

    STANDALONE = "standalone"
    SERVER = "server"


def detect_runtime_mode(
    project_id: str | None = None,
    actor_user_id: str | None = None,
) -> RuntimeMode:
    """현재 런타임 모드를 감지합니다.

    우선순위:
      1. 환경변수 ``THESEUS_RUNTIME_MODE=standalone|server``
      2. ``project_id`` + ``actor_user_id`` 둘 다 존재 → SERVER
      3. 폴백 → STANDALONE
    """
    env = os.getenv("THESEUS_RUNTIME_MODE", "").lower().strip()
    if env in ("standalone", "server"):
        return RuntimeMode(env)
    if project_id is not None and actor_user_id is not None:
        return RuntimeMode.SERVER
    return RuntimeMode.STANDALONE
