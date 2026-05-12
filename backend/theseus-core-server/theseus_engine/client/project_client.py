"""Theseus Project Client.

에이전트가 사용자 PC에서 로컬로 실행될 때 백엔드 서버에서
프로젝트 설정을 받아오고 결과를 동기화하는 클라이언트 레이어.

사용 방법:
    THESEUS_SERVER_URL 환경변수가 설정되어 있으면 서버 모드로 동작.
    설정되어 있지 않으면 standalone 모드로 동작 (서버 통신 없음).

데이터 흐름:
    1. 세션 시작: 서버에서 프로젝트 설정 fetch
       → tool_permissions, custom_tool 코드, rbac_level, system_prompt 추가분
    2. 커스텀 툴 코드를 로컬 custom_tools/{project_id}/ 에 저장
    3. 매 턴 완료 후: 대화 이력 + 토큰 사용량 서버에 전송
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

# 서버 URL 환경변수 — 미설정 시 standalone 모드
_SERVER_URL = os.getenv("THESEUS_SERVER_URL", "").rstrip("/")
_CONNECT_TIMEOUT = float(os.getenv("THESEUS_CLIENT_TIMEOUT", "10"))


# ---------------------------------------------------------------------------
# 설정 데이터 구조
# ---------------------------------------------------------------------------

@dataclass
class CustomToolSpec:
    """서버에서 받은 커스텀 툴 명세."""
    name: str
    filename: str
    code: str
    permission_level: int = 1
    description: str = ""


@dataclass
class ProjectConfig:
    """서버에서 받아온 프로젝트 설정.

    standalone 모드에서는 기본값이 사용된다.
    """
    project_id: str
    actor_role: str = "MEMBER"
    user_level: int = 1
    tool_permissions: dict[str, int] = field(default_factory=dict)
    custom_tools: list[CustomToolSpec] = field(default_factory=list)
    system_prompt_addition: str = ""
    """프로젝트 전용 시스템 프롬프트 추가 내용 (회사 규칙, 컨벤션 등)."""
    session_id: str = ""


# ---------------------------------------------------------------------------
# 프로젝트 클라이언트
# ---------------------------------------------------------------------------

class TheseusProjectClient:
    """백엔드 서버와 통신하는 클라이언트.

    THESEUS_SERVER_URL 미설정 시 모든 메서드가 no-op으로 동작하여
    standalone 모드와 완전히 하위 호환된다.
    """

    def __init__(self, server_url: str = _SERVER_URL) -> None:
        self._url = server_url
        self._enabled = bool(server_url)
        if self._enabled:
            log.info("[ProjectClient] 서버 모드 활성화: %s", server_url)
        else:
            log.debug("[ProjectClient] standalone 모드 (THESEUS_SERVER_URL 미설정)")

    @property
    def is_enabled(self) -> bool:
        """서버 연동 활성화 여부."""
        return self._enabled

    # ── 세션 초기화 ──────────────────────────────────────────────

    async def fetch_project_config(
        self,
        project_id: str,
        token: str,
    ) -> ProjectConfig:
        """서버에서 프로젝트 설정을 가져옵니다.

        Args:
            project_id: 프로젝트 식별자.
            token: Spring Boot 발급 세션 토큰.

        Returns:
            ProjectConfig — 서버 연동 비활성 시 기본값 반환.
        """
        if not self._enabled:
            return ProjectConfig(project_id=project_id)

        try:
            import httpx
            async with httpx.AsyncClient(timeout=_CONNECT_TIMEOUT) as client:
                resp = await client.get(
                    f"{self._url}/api/agent/project-config",
                    params={"projectId": project_id},
                    headers={"Authorization": f"Bearer {token}"},
                )
                resp.raise_for_status()
                data = resp.json()
                return self._parse_project_config(data)
        except Exception as exc:
            log.warning(
                "[ProjectClient] 프로젝트 설정 fetch 실패 — standalone 기본값 사용: %s", exc
            )
            return ProjectConfig(project_id=project_id)

    def _parse_project_config(self, data: dict[str, Any]) -> ProjectConfig:
        """서버 응답 JSON을 ProjectConfig로 변환합니다."""
        custom_tools = [
            CustomToolSpec(
                name=t["name"],
                filename=t["filename"],
                code=t["code"],
                permission_level=t.get("permissionLevel", 1),
                description=t.get("description", ""),
            )
            for t in data.get("customTools", [])
        ]
        return ProjectConfig(
            project_id=data.get("projectId", ""),
            actor_role=data.get("actorRole", "MEMBER"),
            user_level=data.get("userLevel", 1),
            tool_permissions=data.get("toolPermissions", {}),
            custom_tools=custom_tools,
            system_prompt_addition=data.get("systemPromptAddition", ""),
            session_id=data.get("sessionId", ""),
        )

    # ── 커스텀 툴 설치 ────────────────────────────────────────────

    def install_custom_tools(
        self,
        config: ProjectConfig,
        base_dir: Optional[Path] = None,
    ) -> Path:
        """서버에서 받은 커스텀 툴 코드를 로컬에 저장합니다.

        Args:
            config: 서버에서 받은 프로젝트 설정.
            base_dir: 저장 기준 디렉토리. 기본값은 custom_tools/ 디렉토리.

        Returns:
            툴이 저장된 디렉토리 경로.
        """
        if not config.custom_tools:
            return Path("custom_tools") / config.project_id

        from theseus_engine.tools.core.tool_factory import CUSTOM_TOOLS_DIR
        target = (base_dir or Path(CUSTOM_TOOLS_DIR)) / config.project_id
        target.mkdir(parents=True, exist_ok=True)

        for tool in config.custom_tools:
            tool_path = target / tool.filename
            tool_path.write_text(tool.code, encoding="utf-8")
            log.info("[ProjectClient] 커스텀 툴 설치: %s", tool_path)

        return target

    # ── 세션 동기화 ───────────────────────────────────────────────

    async def sync_history(
        self,
        session_id: str,
        messages: list[Any],
        token: str = "",
    ) -> None:
        """대화 이력을 서버에 저장합니다.

        서버 연동 비활성 시 no-op.
        """
        if not self._enabled or not session_id:
            return

        try:
            import httpx
            serialized = [
                m.model_dump() if hasattr(m, "model_dump") else str(m)
                for m in messages
            ]
            async with httpx.AsyncClient(timeout=_CONNECT_TIMEOUT) as client:
                await client.post(
                    f"{self._url}/api/agent/sessions/{session_id}/history",
                    json={"messages": serialized},
                    headers={"Authorization": f"Bearer {token}"},
                )
        except Exception as exc:
            log.warning("[ProjectClient] 이력 동기화 실패: %s", exc)

    async def report_usage(
        self,
        session_id: str,
        usage: dict[str, Any],
        token: str = "",
    ) -> None:
        """토큰 사용량을 서버에 전송합니다 (Zero-Trust 과금).

        서버 연동 비활성 시 no-op.
        """
        if not self._enabled or not session_id:
            return

        try:
            import httpx
            async with httpx.AsyncClient(timeout=_CONNECT_TIMEOUT) as client:
                await client.post(
                    f"{self._url}/internal/billing/usage",
                    json={"sessionId": session_id, **usage},
                    headers={"Authorization": f"Bearer {token}"},
                )
        except Exception as exc:
            log.warning("[ProjectClient] 과금 전송 실패: %s", exc)


# ---------------------------------------------------------------------------
# 편의 함수
# ---------------------------------------------------------------------------

_default_client: Optional[TheseusProjectClient] = None


def get_project_client() -> TheseusProjectClient:
    """전역 프로젝트 클라이언트 인스턴스를 반환합니다."""
    global _default_client
    if _default_client is None:
        _default_client = TheseusProjectClient()
    return _default_client


async def init_project_session(
    project_id: str,
    token: str = "",
    base_dir: Optional[Path] = None,
) -> ProjectConfig:
    """프로젝트 세션을 초기화합니다.

    서버에서 설정을 받아오고 커스텀 툴을 로컬에 설치합니다.
    THESEUS_SERVER_URL 미설정 시 standalone 기본값을 반환합니다.

    Args:
        project_id: 프로젝트 식별자.
        token: Spring Boot 세션 토큰. standalone 시 빈 문자열.
        base_dir: 커스텀 툴 저장 기준 디렉토리.

    Returns:
        ProjectConfig — setup_engine()에 바로 주입 가능한 설정.

    Example:
        config = await init_project_session("backend-team", token=jwt_token)
        engine, registry = await setup_engine(
            sm=sm,
            project_id=config.project_id,
            user_level=config.user_level,
            actor_role=config.actor_role,
            project_tool_permissions=config.tool_permissions,
            cwd=Path.cwd(),
        )
    """
    client = get_project_client()
    config = await client.fetch_project_config(project_id, token)
    client.install_custom_tools(config, base_dir)
    return config
