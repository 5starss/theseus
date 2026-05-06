from openharness.permissions.checker import PermissionChecker, PermissionDecision
from openharness.config.settings import PermissionSettings
from typing import Dict


class TheseusPermissionChecker(PermissionChecker):
    """
    [Phase 2] 역할 기반 접근 제어 (RBAC)
    초기 세팅에서 프로젝트별로 부여된 권한 설정(tool_permissions)을 주입받아,
    자연수 대소 비교를 통해 사용자의 툴 실행 권한을 동적으로 판별합니다.

    require_human_confirm=True  (CLI 기본값)
        → bash/write_file/edit_file은 RBAC를 통과해도 사용자 확인을 요청합니다.
    require_human_confirm=False (서버 기본값)
        → RBAC 레벨이 충분하면 사용자 확인 없이 자동 승인합니다.
    """

    # RBAC를 통과해도 사람의 확인이 필요한 민감한 도구 목록 (CLI 모드 한정)
    SENSITIVE_TOOLS = {"bash", "write_file", "edit_file"}

    def __init__(
        self,
        settings: PermissionSettings,
        user_level: int = 1,
        tool_permissions: Dict[str, int] = None,
        require_human_confirm: bool = True,
    ):
        super().__init__(settings)
        self.user_level = user_level
        self.tool_permissions = tool_permissions or {}
        # CLI(interactive)에서만 True — 서버에서는 False로 호출
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

        # 1단계: RBAC 레벨 체크
        if self.user_level < required_level:
            return PermissionDecision(
                allowed=False,
                requires_confirmation=False,
                reason=(
                    f"[RBAC Denied] User level ({self.user_level}) is insufficient "
                    f"for tool '{tool_name}' (requires level {required_level})."
                ),
            )

        # 2단계: 민감한 도구 — CLI(interactive)에서만 사용자 확인 요청
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
            # 서버 모드: RBAC를 통과했으므로 즉시 승인
            return PermissionDecision(
                allowed=True,
                reason=f"[RBAC Auto-Approved] Server mode, level {self.user_level} >= {required_level}",
            )

        # 3단계: OpenHarness 기본 정책 (SENSITIVE PATH 등)
        decision = super().evaluate(
            tool_name, is_read_only=is_read_only, file_path=file_path, command=command
        )

        # 부모가 사람 확인을 요청한 경우 → RBAC 통과했으므로 자동 승인
        if not decision.allowed and decision.requires_confirmation:
            return PermissionDecision(
                allowed=True,
                reason=f"[RBAC Approved] Level {self.user_level} >= {required_level}",
            )

        return decision

