package com.theseus.api.domain.project.controller;

import com.theseus.api.domain.project.dto.request.ProjectCreateRequest;
import com.theseus.api.domain.project.dto.request.ProjectUpdateRequest;
import com.theseus.api.domain.project.dto.response.ProjectResponse;
import com.theseus.api.domain.project.service.ProjectService;
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
@Tag(name = "Project", description = "프로젝트 관리 API")
@RequestMapping("/projects")
@RestController
public class ProjectController {

	private final ProjectService projectService;

	@GetMapping
	@Operation(summary = "프로젝트 목록 조회", description = "SUPER_ADMIN이 전체 프로젝트 목록을 조회합니다.")
	public ResponseEntity<List<ProjectResponse>> getProjects() {
		return ResponseEntity.ok(projectService.getProjects());
	}

	@GetMapping("/{projectId}")
	@Operation(summary = "프로젝트 단건 조회", description = "SUPER_ADMIN이 프로젝트 상세 정보를 조회합니다.")
	public ResponseEntity<ProjectResponse> getProject(@PathVariable Long projectId) {
		return ResponseEntity.ok(projectService.getProject(projectId));
	}

	@PostMapping
	@Operation(summary = "프로젝트 생성", description = "SUPER_ADMIN이 프로젝트를 생성하고 프로젝트 ADMIN 멤버를 함께 등록합니다.")
	public ResponseEntity<ProjectResponse> createProject(@Valid @RequestBody ProjectCreateRequest request) {
		return ResponseEntity.status(HttpStatus.CREATED)
			.body(projectService.createProject(request));
	}

	@PostMapping("/{projectId}/update")
	@Operation(summary = "프로젝트 수정", description = "SUPER_ADMIN이 프로젝트 이름, 설명, 상태를 수정합니다.")
	public ResponseEntity<ProjectResponse> updateProject(
		@PathVariable Long projectId,
		@Valid @RequestBody ProjectUpdateRequest request
	) {
		return ResponseEntity.ok(projectService.updateProject(projectId, request));
	}

	@PostMapping("/{projectId}/delete")
	@Operation(summary = "프로젝트 비활성화", description = "SUPER_ADMIN이 프로젝트를 물리 삭제하지 않고 INACTIVE 상태로 변경합니다.")
	public ResponseEntity<ProjectResponse> deleteProject(@PathVariable Long projectId) {
		return ResponseEntity.ok(projectService.deleteProject(projectId));
	}
}
