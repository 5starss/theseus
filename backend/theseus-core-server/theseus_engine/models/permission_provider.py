"""ToolPermissionProvider — Standalone/Server 공통 권한 인터페이스.

두 모드(Standalone/Server)가 동일한 계약을 따르므로
engine_builder는 모드에 무관하게 Provider를 통해 권한 정보를 얻는다.

구현체:
  - StandalonePermissionProvider: .meta.json 파일 기반 (CLI/TUI)
  - ServerPermissionProvider: 콜백 함수 위임 방식 (src/auth 연동)
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

log = logging.getLogger(__name__)


# ── 추상 인터페이스 ──────────────────────────────────────────────


class ToolPermissionProvider(ABC):
    """툴 권한 맵을 공급하는 추상 인터페이스."""

    @abstractmethod
    async def get_permissions(self) -> dict[str, int]:
        """``{ tool_name: required_level }`` 맵을 반환합니다."""

    @abstractmethod
    async def get_disabled_tools(self) -> set[str]:
        """현재 컨텍스트에서 완전히 비활성화된 툴 이름 집합을 반환합니다."""

    @abstractmethod
    async def sync_tool(
        self,
        tool_name: str,
        permission_level: int,
        *,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """툴 생성/갱신 후 권한 소스에 변경사항을 반영합니다."""


# ── Standalone 구현체 (CLI/TUI) ──────────────────────────────────


class StandalonePermissionProvider(ToolPermissionProvider):
    """로컬 ``custom_tools/*.meta.json`` + 클래스 속성 기반 구현체.

    - ``get_permissions()``: ``.meta.json``의 ``permissionLevel`` 스캔
    - ``get_disabled_tools()``: ``isActive=False`` 인 툴 수집
    - ``sync_tool()``: ``.meta.json``의 ``permissionLevel`` 갱신
    """

    def __init__(self, custom_tools_dir: str | Path) -> None:
        self._dir = Path(custom_tools_dir)

    async def get_permissions(self) -> dict[str, int]:
        perms: dict[str, int] = {}
        if not self._dir.is_dir():
            return perms
        for meta_file in self._dir.glob("*.meta.json"):
            try:
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                name = data.get("toolName") or meta_file.stem
                level = int(data.get("permissionLevel", 1))
                perms[name] = level
            except Exception as exc:
                log.debug("Failed to read meta %s: %s", meta_file, exc)
        return perms

    async def get_disabled_tools(self) -> set[str]:
        disabled: set[str] = set()
        if not self._dir.is_dir():
            return disabled
        for meta_file in self._dir.glob("*.meta.json"):
            try:
                data = json.loads(meta_file.read_text(encoding="utf-8"))
                if not data.get("isActive", True):
                    name = data.get("toolName") or meta_file.stem
                    disabled.add(name)
            except Exception:
                pass
        return disabled

    async def sync_tool(
        self,
        tool_name: str,
        permission_level: int,
        *,
        meta: dict[str, Any] | None = None,
    ) -> None:
        meta_path = self._dir / f"{tool_name}.meta.json"
        if not meta_path.exists():
            return
        try:
            data = json.loads(meta_path.read_text(encoding="utf-8"))
            data["permissionLevel"] = permission_level
            if meta:
                data.update(meta)
            meta_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            log.info(
                "StandalonePermissionProvider.sync_tool: %s → Lv.%d",
                tool_name,
                permission_level,
            )
        except Exception as exc:
            log.warning("StandalonePermissionProvider.sync_tool failed: %s", exc)


# ── Server 구현체 (FastAPI/Spring 위임) ──────────────────────────


class ServerPermissionProvider(ToolPermissionProvider):
    """Spring Backend API 위임 구현체.

    ``theseus_engine`` 는 ``src/auth`` 를 직접 import 하지 않는다.
    대신 호출 측(``src/builder/engine.py``)이 콜백 함수를 주입한다.

    Example::

        provider = ServerPermissionProvider(
            fetch_permissions_func=lambda: get_project_tool_permissions(pid, uid),
            fetch_disabled_func=lambda: get_project_disabled_tools(pid),
            sync_func=lambda name, level, meta: patch_project_tool(pid, name, level),
        )
    """

    def __init__(
        self,
        fetch_permissions_func: Callable[[], Awaitable[dict[str, int]]],
        fetch_disabled_func: Optional[Callable[[], Awaitable[set[str]]]] = None,
        sync_func: Optional[
            Callable[[str, int, Optional[dict[str, Any]]], Awaitable[None]]
        ] = None,
    ) -> None:
        self._fetch = fetch_permissions_func
        self._fetch_disabled = fetch_disabled_func
        self._sync = sync_func

    async def get_permissions(self) -> dict[str, int]:
        return await self._fetch()

    async def get_disabled_tools(self) -> set[str]:
        if self._fetch_disabled:
            return await self._fetch_disabled()
        return set()

    async def sync_tool(
        self,
        tool_name: str,
        permission_level: int,
        *,
        meta: dict[str, Any] | None = None,
    ) -> None:
        if self._sync:
            await self._sync(tool_name, permission_level, meta)
        else:
            log.debug(
                "ServerPermissionProvider.sync_tool: no sync_func configured, "
                "skipping sync for %s",
                tool_name,
            )
