from openharness.permissions.checker import PermissionChecker, PermissionDecision
from openharness.config.settings import PermissionSettings
from typing import Dict

class TheseusPermissionChecker(PermissionChecker):
    """
    [Phase 2] 역할 기반 접근 제어 (RBAC)
    초기 세팅에서 프로젝트별로 부여된 권한 설정(tool_permissions)을 주입받아,
    자연수 대소 비교를 통해 사용자의 툴 실행 권한을 동적으로 판별합니다.
    """
    def __init__(
        self, 
        settings: PermissionSettings, 
        user_level: int = 1, 
        tool_permissions: Dict[str, int] = None
    ):
        super().__init__(settings)
        # 사용자의 현재 권한 레벨 (자연수)
        self.user_level = user_level
        
        # 프로젝트별 동적 툴 권한 맵핑 (tool_name -> required_level)
        # 기본값으로 빈 딕셔너리를 사용하며, 미지정 툴은 기본 레벨(1)로 간주합니다.
        self.tool_permissions = tool_permissions or {}

        # [Theseus] 민감한 도구 목록: RBAC 레벨을 통과하더라도 항상 사용자에게 확인을 요청합니다.
        self.always_confirm_tools = {"bash", "write_file", "edit_file"}
        
    def evaluate(self, tool_name: str, *, is_read_only: bool, file_path: str | None = None, command: str | None = None) -> PermissionDecision:
        # 설정에 없는 툴은 최소 권한(1)을 요구한다고 가정
        required_level = self.tool_permissions.get(tool_name, 1)
        
        # 자연수 대소 비교 (사용자 레벨 >= 요구 레벨)
        if self.user_level < required_level:
            return PermissionDecision(
                allowed=False,
                requires_confirmation=False,
                reason=f"[RBAC Denied] User level ({self.user_level}) is insufficient for tool '{tool_name}' (requires level {required_level})."
            )
            
        # [Theseus] always_confirm_tools에 포함된 도구는 RBAC 통과 후에도 항상 사용자 확인을 거칩니다.
        if tool_name in self.always_confirm_tools:
            return PermissionDecision(
                allowed=False,
                requires_confirmation=True,
                reason=f"[Security Policy] '{tool_name}' is a sensitive tool and requires explicit user approval."
            )

        # 권한이 충분하면 부모 클래스의 기본 정책(SENSITIVE PATH 필터링 등)을 우선 검사합니다.
        decision = super().evaluate(tool_name, is_read_only=is_read_only, file_path=file_path, command=command)
        
        # 부모 클래스가 '수정 권한 도구(Mutating)'라서 사람의 확인이 필요하다고 막았다면,
        # 우리의 RBAC를 통과했으므로 자동 승인 처리합니다. (단, SENSITIVE PATH 차단 등은 유지)
        if not decision.allowed and decision.requires_confirmation:
            return PermissionDecision(allowed=True, reason=f"[RBAC Approved] Level {self.user_level} >= {required_level}")
            
        return decision

