package com.theseus.api.domain.project.controller;

import com.theseus.api.domain.project.dto.request.ProjectMemberCreateRequest;
import com.theseus.api.domain.project.dto.request.ProjectMemberUpdateRequest;
import com.theseus.api.domain.project.dto.response.ProjectMemberResponse;
import com.theseus.api.domain.project.service.ProjectMemberService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RequiredArgsConstructor
@Tag(name = "ProjectMember", description = "프로젝트 멤버 관리 API")
@RestController
public class ProjectMemberController {

	private final ProjectMemberService projectMemberService;

	@GetMapping("/projects/{projectId}/members")
	@Operation(summary = "프로젝트 멤버 목록 조회", description = "프로젝트 ADMIN이 프로젝트 멤버 목록을 조회합니다.")
	public ResponseEntity<List<ProjectMemberResponse>> getProjectMembers(@PathVariable Long projectId) {
		return ResponseEntity.ok(projectMemberService.getProjectMembers(projectId));
	}

	@PostMapping("/projects/{projectId}/members")
	@Operation(summary = "프로젝트 멤버 등록", description = "프로젝트 ADMIN이 사용자를 프로젝트 멤버로 등록합니다.")
	public ResponseEntity<ProjectMemberResponse> createProjectMember(
		@PathVariable Long projectId,
		@Valid @RequestBody ProjectMemberCreateRequest request
	) {
		return ResponseEntity.status(HttpStatus.CREATED)
			.body(projectMemberService.createProjectMember(projectId, request));
	}

	@GetMapping("/project-members/{projectMemberId}")
	@Operation(summary = "프로젝트 멤버 단건 조회", description = "프로젝트 ADMIN이 프로젝트 멤버 상세 정보를 조회합니다.")
	public ResponseEntity<ProjectMemberResponse> getProjectMember(@PathVariable Long projectMemberId) {
		return ResponseEntity.ok(projectMemberService.getProjectMember(projectMemberId));
	}

	@PostMapping("/project-members/{projectMemberId}/update")
	@Operation(summary = "프로젝트 멤버 수정", description = "프로젝트 ADMIN이 프로젝트 멤버 역할과 Tool 권한을 수정합니다.")
	public ResponseEntity<ProjectMemberResponse> updateProjectMember(
		@PathVariable Long projectMemberId,
		@Valid @RequestBody ProjectMemberUpdateRequest request
	) {
		return ResponseEntity.ok(projectMemberService.updateProjectMember(projectMemberId, request));
	}

	@PostMapping("/project-members/{projectMemberId}/delete")
	@Operation(summary = "프로젝트 멤버 완료 처리", description = "프로젝트 ADMIN이 프로젝트 멤버를 완료 상태로 변경합니다.")
	public ResponseEntity<ProjectMemberResponse> deleteProjectMember(@PathVariable Long projectMemberId) {
		return ResponseEntity.ok(projectMemberService.deleteProjectMember(projectMemberId));
	}
}
