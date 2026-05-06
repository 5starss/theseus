package com.theseus.api.domain.project.controller;

import com.theseus.api.common.response.ApiResponse;
import com.theseus.api.common.response.status.SuccessCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.project.dto.request.ProjectMemberCreateRequest;
import com.theseus.api.domain.project.dto.request.ProjectMemberUpdateRequest;
import com.theseus.api.domain.project.dto.response.ProjectMemberResponse;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.service.ProjectMemberService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@Tag(name = "ProjectMember", description = "프로젝트 멤버 관리 API")
@RequestMapping("/api/v1/projects/{projectId}")
public class ProjectMemberController {

    private final ProjectMemberService projectMemberService;

    @Operation(summary = "프로젝트 멤버 목록 조회", description = "프로젝트에 속한 멤버 목록을 조회합니다. status가 없으면 진행 중인 멤버만 조회합니다.")
    @GetMapping("/members")
    public ResponseEntity<ApiResponse<List<ProjectMemberResponse>>> getProjectMembers(
            @AuthenticationPrincipal AuthenticatedUser currentUser,
            @PathVariable Long projectId,
            @RequestParam(required = false) String status
    ) {
        ProjectMemberStatus memberStatus = parseMemberStatus(status);
        List<ProjectMemberResponse> responses = projectMemberService.getProjectMembers(currentUser, projectId, memberStatus);
        return ApiResponse.onSuccess(SuccessCode.OK, responses);
    }

    @Operation(summary = "프로젝트 멤버 등록", description = "프로젝트 ADMIN이 활성 사용자를 프로젝트 멤버로 등록합니다. ADMIN으로 등록해도 프로젝트 담당자(PM)는 변경되지 않습니다.")
    @PostMapping("/members")
    public ResponseEntity<ApiResponse<ProjectMemberResponse>> createProjectMember(
            @AuthenticationPrincipal AuthenticatedUser currentUser,
            @PathVariable Long projectId,
            @Valid @RequestBody ProjectMemberCreateRequest request
    ) {
        ProjectMemberResponse response = projectMemberService.createProjectMember(currentUser, projectId, request);
        return ApiResponse.onSuccess(SuccessCode.CREATED, response);
    }

    @Operation(summary = "내 프로젝트 권한 조회", description = "JWT 사용자 기준으로 해당 프로젝트의 내 멤버 권한과 프로젝트 담당자 여부를 조회합니다.")
    @GetMapping("/me")
    public ResponseEntity<ApiResponse<ProjectMemberResponse>> getMyProjectMember(
            @AuthenticationPrincipal AuthenticatedUser currentUser,
            @PathVariable Long projectId
    ) {
        ProjectMemberResponse response = projectMemberService.getMyProjectMember(currentUser, projectId);
        return ApiResponse.onSuccess(SuccessCode.OK, response);
    }

    @Operation(summary = "프로젝트 멤버 권한 수정", description = "프로젝트 ADMIN이 멤버 권한을 수정합니다. 현재 프로젝트 담당자(PM)는 ADMIN/진행중 상태에서 제외할 수 없습니다.")
    @PatchMapping("/members/{projectMemberId}")
    public ResponseEntity<ApiResponse<ProjectMemberResponse>> updateProjectMember(
            @AuthenticationPrincipal AuthenticatedUser currentUser,
            @PathVariable Long projectId,
            @PathVariable Long projectMemberId,
            @Valid @RequestBody ProjectMemberUpdateRequest request
    ) {
        ProjectMemberResponse response = projectMemberService.updateProjectMember(currentUser, projectId, projectMemberId, request);
        return ApiResponse.onSuccess(SuccessCode.OK, response);
    }

    private ProjectMemberStatus parseMemberStatus(String status) {
        if (status == null || status.isBlank()) {
            return ProjectMemberStatus.IN_PROGRESS;
        }

        return ProjectMemberStatus.createFrom(status);
    }
}
