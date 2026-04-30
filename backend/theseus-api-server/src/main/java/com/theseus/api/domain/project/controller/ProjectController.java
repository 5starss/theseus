package com.theseus.api.domain.project.controller;

import com.theseus.api.common.response.ApiResponse;
import com.theseus.api.common.response.status.SuccessCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.project.dto.request.ProjectCreateRequest;
import com.theseus.api.domain.project.dto.request.ProjectUpdateRequest;
import com.theseus.api.domain.project.dto.response.MyProjectResponse;
import com.theseus.api.domain.project.dto.response.ProjectPageResponse;
import com.theseus.api.domain.project.dto.response.ProjectResponse;
import com.theseus.api.domain.project.dto.response.ProjectSummaryResponse;
import com.theseus.api.domain.project.entity.ProjectStatus;
import com.theseus.api.domain.project.service.ProjectService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
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
@Tag(name = "Project", description = "프로젝트 관리 API")
@RequestMapping("/api/v1")
public class ProjectController {

    private final ProjectService projectService;

    @Operation(summary = "내 프로젝트 목록 조회", description = "JWT 사용자 기준으로 진행 중인 프로젝트 멤버십과 프로젝트 담당자 여부를 조회합니다.")
    @GetMapping("/projects")
    public ResponseEntity<ApiResponse<ProjectPageResponse<MyProjectResponse>>> getMyProjects(
            @AuthenticationPrincipal AuthenticatedUser currentUser,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size
    ) {
        Page<MyProjectResponse> projects = projectService.getMyProjects(currentUser, page, size);
        return ApiResponse.onSuccess(SuccessCode.OK, ProjectPageResponse.createFrom(projects));
    }

    @Operation(summary = "전체 프로젝트 목록 조회", description = "Super Admin이 프로젝트 목록을 상태별로 조회합니다.")
    @GetMapping("/admin/projects")
    public ResponseEntity<ApiResponse<ProjectPageResponse<ProjectSummaryResponse>>> getProjects(
            @AuthenticationPrincipal AuthenticatedUser currentUser,
            @RequestParam(required = false) ProjectStatus status,
            @RequestParam(defaultValue = "0") int page,
            @RequestParam(defaultValue = "20") int size
    ) {
        Page<ProjectSummaryResponse> projects = projectService.getProjects(currentUser, status, page, size);
        return ApiResponse.onSuccess(SuccessCode.OK, ProjectPageResponse.createFrom(projects));
    }

    @Operation(summary = "프로젝트 단건 조회", description = "Super Admin은 모든 프로젝트를 조회할 수 있고, 프로젝트 멤버는 본인이 속한 활성 프로젝트만 조회할 수 있습니다.")
    @GetMapping("/projects/{projectId}")
    public ResponseEntity<ApiResponse<ProjectResponse>> getProject(
            @AuthenticationPrincipal AuthenticatedUser currentUser,
            @PathVariable Long projectId
    ) {
        ProjectResponse response = projectService.getProject(currentUser, projectId);
        return ApiResponse.onSuccess(SuccessCode.OK, response);
    }

    @Operation(summary = "프로젝트 생성", description = "Super Admin이 프로젝트를 생성하고, 활성 사용자 중 사번과 이름이 일치하는 사용자를 프로젝트 담당자(PM)로 지정합니다.")
    @PostMapping("/projects")
    public ResponseEntity<ApiResponse<ProjectResponse>> createProject(
            @AuthenticationPrincipal AuthenticatedUser currentUser,
            @Valid @RequestBody ProjectCreateRequest request
    ) {
        ProjectResponse response = projectService.createProject(currentUser, request);
        return ApiResponse.onSuccess(SuccessCode.CREATED, response);
    }

    @Operation(summary = "프로젝트 정보 수정", description = "프로젝트 기본 정보는 Super Admin 또는 프로젝트 ADMIN이 수정할 수 있고, 프로젝트 담당자(PM) 변경은 Super Admin만 수행할 수 있습니다.")
    @PatchMapping("/projects/{projectId}")
    public ResponseEntity<ApiResponse<ProjectResponse>> updateProject(
            @AuthenticationPrincipal AuthenticatedUser currentUser,
            @PathVariable Long projectId,
            @Valid @RequestBody ProjectUpdateRequest request
    ) {
        ProjectResponse response = projectService.updateProject(currentUser, projectId, request);
        return ApiResponse.onSuccess(SuccessCode.OK, response);
    }
}
