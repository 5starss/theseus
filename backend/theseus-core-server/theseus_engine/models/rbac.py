"""Theseus RBAC permission checker/settings.

QueryEngine이 duck-typing으로 ``evaluate(tool_name, *, is_read_only, file_path, command)``
인터페이스만 요구하므로 동일한 프로토콜을 자체 구현합니다.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from enum import Enum
from typing import Dict


class PermissionMode(str, Enum):
    """Theseus permission modes."""
    DEFAULT = "default"
    PLAN = "plan"
    FULL_AUTO = "full_auto"

# QueryEngine이 기대하는 반환 타입 — Theseus 자체 정의
@dataclass(frozen=True)
class PermissionDecision:
    """Result of checking whether a tool invocation may run."""
    allowed: bool
    requires_confirmation: bool = False
    reason: str = ""


# Theseus permission settings
class TheseusPermissionSettings:
    """Theseus 자체 권한 설정."""
    def __init__(self) -> None:
        self.allowed_tools: list[str] = []
        self.denied_tools: list[str] = []
        self.denied_commands: list[str] = []


# 민감한 자격증명 경로 패턴
SENSITIVE_PATH_PATTERNS: tuple[str, ...] = (
    "*/.ssh/*",
    "*/.aws/credentials",
    "*/.aws/config",
    "*/.config/gcloud/*",
    "*/.azure/*",
    "*/.gnupg/*",
    "*/.docker/config.json",
    "*/.kube/config",
)


class TheseusPermissionChecker:
    """Theseus RBAC 권한 체커.

    QueryEngine이 duck-typing으로 ``evaluate()``를 호출하므로
    동일한 메서드 시그니처를 유지합니다.
    """

    SENSITIVE_TOOLS = {"bash", "write_file", "edit_file"}

    def __init__(
        self,
        settings: TheseusPermissionSettings,
        user_level: int = 1,
        tool_permissions: Dict[str, int] | None = None,
        require_human_confirm: bool = True,
    ):
        self._settings = settings
        self.user_level = user_level
        self.tool_permissions = tool_permissions or {}
        self.require_human_confirm = require_human_confirm

    def evaluate(
        self,
        tool_name: str,
        *,
        is_read_only: bool,
        file_path: str | None = None,
        command: str | None = None,
    ) -> PermissionDecision:
        required_level = self.tool_permissions.get(tool_name, 1)

        # 민감 경로 보호
        if file_path:
            # Windows/Unix 경로 통일: 백슬래시 → 슬래시로 정규화
            posix_path = file_path.replace("\\", "/").rstrip("/")
            for candidate in (posix_path, posix_path + "/"):
                for pattern in SENSITIVE_PATH_PATTERNS:
                    if fnmatch.fnmatch(candidate, pattern):
                        return PermissionDecision(
                            allowed=False,
                            reason=f"Access denied: {file_path} matches sensitive path pattern '{pattern}'",
                        )

        # RBAC 레벨 체크
        if self.user_level < required_level:
            return PermissionDecision(
                allowed=False,
                requires_confirmation=False,
                reason=(
                    f"[RBAC Denied] User level ({self.user_level}) is insufficient "
                    f"for tool '{tool_name}' (requires level {required_level})."
                ),
            )

        # 민감한 도구 — CLI에서만 사용자 확인 요청
        if tool_name in self.SENSITIVE_TOOLS:
            if self.require_human_confirm:
                return PermissionDecision(
                    allowed=False,
                    requires_confirmation=True,
                    reason=(
                        f"[Security Policy] '{tool_name}' is a sensitive tool "
                        f"and requires explicit user approval."
                    ),
                )
            return PermissionDecision(
                allowed=True,
                reason=f"[RBAC Auto-Approved] Server mode, level {self.user_level} >= {required_level}",
            )

        # 명시적 도구 거부/허용
        if tool_name in self._settings.denied_tools:
            return PermissionDecision(allowed=False, reason=f"{tool_name} is explicitly denied")
        if tool_name in self._settings.allowed_tools:
            return PermissionDecision(allowed=True, reason=f"{tool_name} is explicitly allowed")

        # 명령어 거부 패턴
        if command:
            for pattern in self._settings.denied_commands:
                if isinstance(pattern, str) and fnmatch.fnmatch(command, pattern):
                    return PermissionDecision(
                        allowed=False,
                        reason=f"Command matches deny pattern: {pattern}",
                    )

        # 읽기 전용 도구는 항상 허용
        if is_read_only:
            return PermissionDecision(allowed=True, reason="read-only tools are allowed")

        # RBAC 통과 → 자동 승인
        return PermissionDecision(
            allowed=True,
            reason=f"[RBAC Approved] Level {self.user_level} >= {required_level}",
        )

