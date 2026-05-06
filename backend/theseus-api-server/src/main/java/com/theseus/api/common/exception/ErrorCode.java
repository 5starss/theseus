package com.theseus.api.common.exception;

import lombok.AllArgsConstructor;
import lombok.Getter;
import org.springframework.http.HttpStatus;

@Getter
@AllArgsConstructor
public enum ErrorCode {

    // Common
    INVALID_INPUT_VALUE(HttpStatus.BAD_REQUEST, "COMMON-001", "잘못된 입력값입니다."),
    INTERNAL_SERVER_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "COMMON-002", "서버 내부 오류가 발생했습니다."),
    METHOD_NOT_ALLOWED(HttpStatus.METHOD_NOT_ALLOWED, "COMMON-003", "지원하지 않는 HTTP 메서드입니다."),
    HANDLE_ACCESS_DENIED(HttpStatus.FORBIDDEN, "COMMON-004", "접근 권한이 없습니다."),
    
    // Auth
    UNAUTHORIZED(HttpStatus.UNAUTHORIZED, "AUTH-001", "인증되지 않은 사용자입니다."),
    LOGIN_FAILED(HttpStatus.UNAUTHORIZED, "AUTH-002", "아이디 또는 비밀번호가 올바르지 않습니다."),
    INVALID_REFRESH_TOKEN(HttpStatus.UNAUTHORIZED, "AUTH-003", "유효하지 않은 Refresh Token입니다."),
    INTERNAL_API_UNAUTHORIZED(HttpStatus.UNAUTHORIZED, "AUTH-004", "내부 API 인증에 실패했습니다."),
    INVALID_TOKEN_TYPE(HttpStatus.UNAUTHORIZED, "AUTH-005", "지원하지 않는 토큰 타입입니다."),
    
    // User
    USER_NOT_FOUND(HttpStatus.NOT_FOUND, "USER-001", "존재하지 않는 사용자입니다."),
    DUPLICATE_EMPLOYEE_NUMBER(HttpStatus.CONFLICT, "USER-002", "이미 존재하는 사번입니다."),
    DUPLICATE_EMAIL(HttpStatus.CONFLICT, "USER-003", "이미 존재하는 이메일입니다."),
    ACTIVE_PROJECT_ADMIN_USER(HttpStatus.CONFLICT, "USER-004", "활성 프로젝트 담당자는 비활성화할 수 없습니다."),

    
    // Project
    PROJECT_NOT_FOUND(HttpStatus.NOT_FOUND, "PROJ-001", "존재하지 않는 프로젝트입니다."),
    PROJECT_ADMIN_USER_NOT_FOUND(HttpStatus.NOT_FOUND, "PROJ-002", "프로젝트 담당자를 찾을 수 없습니다."),
    PROJECT_ADMIN_REQUEST_REQUIRED(HttpStatus.BAD_REQUEST, "PROJ-003", "프로젝트 담당자 사번과 이름을 모두 입력해야 합니다."),
    PROJECT_ADMIN_USER_ACTIVE_REQUIRED(HttpStatus.CONFLICT, "PROJ-004", "활성 사용자만 프로젝트 담당자로 지정할 수 있습니다."),
    PROJECT_ADMIN_PERMISSION_REQUIRED(HttpStatus.FORBIDDEN, "PROJ-005", "프로젝트 ADMIN 권한이 필요합니다."),
    SUPER_ADMIN_PERMISSION_REQUIRED(HttpStatus.FORBIDDEN, "PROJ-006", "SUPER_ADMIN 권한이 필요합니다."),
    ACTIVE_PROJECT_REQUIRED(HttpStatus.FORBIDDEN, "PROJ-007", "활성 프로젝트만 접근할 수 있습니다."),

    // ProjectMember
    PROJECT_MEMBER_NOT_FOUND(HttpStatus.NOT_FOUND, "PMEM-001", "프로젝트 멤버를 찾을 수 없습니다."),
    PROJECT_MEMBER_PERMISSION_REQUIRED(HttpStatus.FORBIDDEN, "PMEM-002", "프로젝트 멤버 권한이 필요합니다."),
    ACTIVE_PROJECT_MEMBER_REQUIRED(HttpStatus.FORBIDDEN, "PMEM-003", "진행 중인 프로젝트 멤버만 접근할 수 있습니다."),
    DUPLICATE_PROJECT_MEMBER(HttpStatus.CONFLICT, "PMEM-004", "이미 등록된 프로젝트 멤버입니다."),
    PROJECT_ADMIN_MEMBER_REQUIRED(HttpStatus.CONFLICT, "PMEM-005", "프로젝트 담당자는 ADMIN/진행중 상태를 유지해야 합니다."),
    PROJECT_MEMBER_ACTIVE_USER_REQUIRED(HttpStatus.CONFLICT, "PMEM-006", "활성 사용자만 프로젝트 멤버로 등록할 수 있습니다."),
    INVALID_PROJECT_MEMBER_STATUS(HttpStatus.BAD_REQUEST, "PMEM-007", "지원하지 않는 프로젝트 멤버 상태입니다."),

    // Chat
    CHAT_SESSION_NOT_FOUND(HttpStatus.NOT_FOUND, "CHAT-001", "채팅 세션을 찾을 수 없습니다."),
    CLOSED_CHAT_SESSION(HttpStatus.CONFLICT, "CHAT-002", "종료된 채팅 세션에는 메시지를 등록할 수 없습니다."),
    TOOL_CHAT_SESSION_MISMATCH(HttpStatus.BAD_REQUEST, "CHAT-003", "Tool이 해당 채팅 세션에 속하지 않습니다."),

    // Tool
    TOOL_NOT_FOUND(HttpStatus.NOT_FOUND, "TOOL-001", "Tool을 찾을 수 없습니다."),
    UNSUPPORTED_TOOL_SCOPE(HttpStatus.BAD_REQUEST, "TOOL-002", "지원하지 않는 Tool 조회 범위입니다."),
    APPROVED_TOOL_ONLY(HttpStatus.BAD_REQUEST, "TOOL-003", "승인된 Tool만 조회할 수 있습니다."),
    TOOL_USE_PERMISSION_REQUIRED(HttpStatus.FORBIDDEN, "TOOL-004", "Tool 사용 권한이 필요합니다."),
    TOOL_ACCESS_LEVEL_REQUIRED(HttpStatus.FORBIDDEN, "TOOL-005", "Tool 접근 레벨이 부족합니다."),
    TOOL_CREATE_PERMISSION_REQUIRED(HttpStatus.FORBIDDEN, "TOOL-006", "Tool 생성 권한이 필요합니다."),
    TOOL_UPDATE_PERMISSION_REQUIRED(HttpStatus.FORBIDDEN, "TOOL-007", "Tool 수정 권한이 필요합니다."),
    DUPLICATE_TOOL_FILE_NAME(HttpStatus.CONFLICT, "TOOL-008", "이미 존재하는 Tool 파일명입니다."),
    TOOL_REGENERATION_STATUS_REQUIRED(HttpStatus.CONFLICT, "TOOL-009", "DRAFT 또는 REJECTED Tool만 재생성할 수 있습니다."),
    TOOL_FILE_NAME_REQUIRED(HttpStatus.BAD_REQUEST, "TOOL-010", "Tool 파일명은 비어 있을 수 없습니다."),
    TOOL_DRAFT_VERSION_MISMATCH(HttpStatus.CONFLICT, "TOOL-011", "최신 Tool PLAN 버전과 일치하지 않습니다."),

    // ToolApproval
    TOOL_APPROVAL_NOT_FOUND(HttpStatus.NOT_FOUND, "TAPP-001", "Tool 승인 요청을 찾을 수 없습니다."),
    TOOL_APPROVAL_CREATOR_REQUIRED(HttpStatus.FORBIDDEN, "TAPP-002", "Tool 생성자만 승인 요청할 수 있습니다."),
    TOOL_APPROVAL_REVIEW_PHASE_REQUIRED(HttpStatus.CONFLICT, "TAPP-003", "REVIEW 단계의 Draft Tool만 승인 요청할 수 있습니다."),
    TOOL_APPROVAL_REVIEWER_REQUIRED(HttpStatus.FORBIDDEN, "TAPP-004", "프로젝트 ADMIN 또는 MANAGER 권한이 필요합니다."),
    TOOL_APPROVAL_ALREADY_REVIEWED(HttpStatus.CONFLICT, "TAPP-005", "이미 검토된 Tool 승인 요청입니다."),
    TOOL_APPROVAL_PENDING_TOOL_REQUIRED(HttpStatus.CONFLICT, "TAPP-006", "승인 대기 중인 Tool만 검토할 수 있습니다."),
    TOOL_APPROVAL_REQUEST_NUMBER_INVALID(HttpStatus.BAD_REQUEST, "TAPP-007", "Tool 승인 요청 번호는 1 이상이어야 합니다."),

    // ToolGeneration
    TOOL_GENERATION_EVENT_INVALID(HttpStatus.BAD_REQUEST, "TGEN-001", "유효하지 않은 Tool 생성 이벤트입니다."),

    // Billing
    BILLING_USAGE_TOKEN_INVALID(HttpStatus.BAD_REQUEST, "BILL-001", "토큰 사용량은 0 이상이어야 합니다."),
    BILLING_USAGE_PAYLOAD_INVALID(HttpStatus.BAD_REQUEST, "BILL-002", "유효하지 않은 Billing 사용량 요청입니다.");

    private final HttpStatus status;
    private final String code;
    private final String message;

    public boolean isSuccess() {
        return false;
    }
}
