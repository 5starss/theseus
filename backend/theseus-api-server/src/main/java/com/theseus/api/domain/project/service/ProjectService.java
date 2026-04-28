package com.theseus.api.domain.project.service;

import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.project.dto.request.ProjectCreateRequest;
import com.theseus.api.domain.project.dto.request.ProjectUpdateRequest;
import com.theseus.api.domain.project.dto.response.ProjectResponse;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.entity.ProjectStatus;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.user.entity.SystemRole;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ProjectService {

	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final UserRepository userRepository;

	public List<ProjectResponse> getProjects() {
		User currentUser = getCurrentUserEntity();
		validateSuperAdmin(currentUser);

		return projectRepository.findAll().stream()
			.map(ProjectResponse::createFrom)
			.toList();
	}

	public ProjectResponse getProject(Long projectId) {
		User currentUser = getCurrentUserEntity();
		validateSuperAdmin(currentUser);
		Project project = getProjectEntity(projectId);

		return ProjectResponse.createFrom(project);
	}

	@Transactional
	public ProjectResponse createProject(ProjectCreateRequest request) {
		User currentUser = getCurrentUserEntity();
		validateSuperAdmin(currentUser);

		User adminUser = getUserEntity(request.getAdminUserId());
		Project project = projectRepository.save(request.toEntity(currentUser));
		ProjectMember adminMember = ProjectMember.builder()
			.project(project)
			.user(adminUser)
			.projectRole(ProjectRole.ADMIN)
			.accessLevel(1)
			.canCreateTool(true)
			.canUseTool(true)
			.canUpdateTool(true)
			.canDeleteTool(true)
			.createdByUser(currentUser)
			.build();
		projectMemberRepository.save(adminMember);

		return ProjectResponse.createFrom(project);
	}

	@Transactional
	public ProjectResponse updateProject(Long projectId, ProjectUpdateRequest request) {
		User currentUser = getCurrentUserEntity();
		validateSuperAdmin(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectStatus status = request.getStatus() == null ? project.getStatus() : request.getStatus();

		project.update(request.getName(), request.getDescription(), status);

		return ProjectResponse.createFrom(project);
	}

	@Transactional
	public ProjectResponse deleteProject(Long projectId) {
		User currentUser = getCurrentUserEntity();
		validateSuperAdmin(currentUser);
		Project project = getProjectEntity(projectId);

		project.deactivate();

		return ProjectResponse.createFrom(project);
	}

	public Project getProjectEntity(Long projectId) {
		return projectRepository.findById(projectId)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "프로젝트를 찾을 수 없습니다."));
	}

	private User getCurrentUserEntity() {
		Authentication authentication = SecurityContextHolder.getContext().getAuthentication();

		if (authentication == null || !(authentication.getPrincipal() instanceof AuthenticatedUser authenticatedUser)) {
			throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "인증 정보가 없습니다.");
		}

		return getUserEntity(authenticatedUser.userId());
	}

	private User getUserEntity(Long userId) {
		return userRepository.findById(userId)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "사용자를 찾을 수 없습니다."));
	}

	private void validateSuperAdmin(User user) {
		if (!SystemRole.SUPER_ADMIN.equals(user.getSystemRole())) {
			throw new ResponseStatusException(HttpStatus.FORBIDDEN, "SUPER_ADMIN 권한이 필요합니다.");
		}
	}
}
