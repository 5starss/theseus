package com.theseus.api.domain.project.service;

import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.project.dto.request.ProjectCreateRequest;
import com.theseus.api.domain.project.dto.request.ProjectUpdateRequest;
import com.theseus.api.domain.project.dto.response.MyProjectResponse;
import com.theseus.api.domain.project.dto.response.ProjectResponse;
import com.theseus.api.domain.project.dto.response.ProjectSummaryResponse;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.entity.ProjectStatus;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.user.entity.SystemRole;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.entity.UserStatus;
import com.theseus.api.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.http.HttpStatus;
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

	public Page<MyProjectResponse> getMyProjects(AuthenticatedUser currentUser, int page, int size) {
		User user = getCurrentUserEntity(currentUser);
		Pageable pageable = createPageable(page, size);

		return projectMemberRepository.findByUserAndStatusAndProject_Status(
				user,
				ProjectMemberStatus.IN_PROGRESS,
				ProjectStatus.ACTIVE,
				pageable
			)
			.map(MyProjectResponse::createFrom);
	}

	public Page<ProjectSummaryResponse> getProjects(
		AuthenticatedUser currentUser,
		ProjectStatus status,
		int page,
		int size
	) {
		User user = getCurrentUserEntity(currentUser);
		validateSuperAdmin(user);
		Pageable pageable = createPageable(page, size);

		if (status == null) {
			return projectRepository.findAll(pageable)
				.map(ProjectSummaryResponse::createFrom);
		}

		return projectRepository.findByStatus(status, pageable)
			.map(ProjectSummaryResponse::createFrom);
	}

	@Transactional
	public ProjectResponse createProject(AuthenticatedUser currentUser, ProjectCreateRequest request) {
		User createdByUser = getCurrentUserEntity(currentUser);
		validateSuperAdmin(createdByUser);

		User projectAdminUser = getProjectAdminUser(request.getAdminEmployeeNumber(), request.getAdminName());
		validateActiveUser(projectAdminUser, "활성 사용자만 프로젝트 담당자로 지정할 수 있습니다.");

		Project project = projectRepository.save(request.toEntity(createdByUser, projectAdminUser));
		ProjectMember adminMember = createProjectAdminMember(project, projectAdminUser, createdByUser);

		return ProjectResponse.createOf(project, adminMember);
	}

	@Transactional
	public ProjectResponse updateProject(AuthenticatedUser currentUser, Long projectId, ProjectUpdateRequest request) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);

		if (request.hasProjectAdminUpdate()) {
			validateSuperAdmin(user);
			validateProjectAdminRequest(request);
		} else {
			validateProjectUpdater(project, user);
		}

		project.update(request.getName(), request.getDescription(), request.getStatus());

		if (!request.hasProjectAdminUpdate()) {
			return ProjectResponse.createOf(project, findProjectAdminMember(project));
		}

		User projectAdminUser = getProjectAdminUser(request.getAdminEmployeeNumber(), request.getAdminName());
		validateActiveUser(projectAdminUser, "활성 사용자만 프로젝트 담당자로 지정할 수 있습니다.");
		project.updateProjectAdminUser(projectAdminUser);
		ProjectMember adminMember = ensureProjectAdminMember(project, projectAdminUser, user);

		return ProjectResponse.createOf(project, adminMember);
	}

	public Project getProjectEntity(Long projectId) {
		return projectRepository.findById(projectId)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "프로젝트를 찾을 수 없습니다."));
	}

	private ProjectMember createProjectAdminMember(Project project, User projectAdminUser, User createdByUser) {
		ProjectMember projectMember = ProjectMember.builder()
			.project(project)
			.user(projectAdminUser)
			.projectRole(ProjectRole.ADMIN)
			.accessLevel(1)
			.canCreateTool(true)
			.canUseTool(true)
			.canUpdateTool(true)
			.canDeleteTool(true)
			.createdByUser(createdByUser)
			.build();

		return projectMemberRepository.save(projectMember);
	}

	private ProjectMember ensureProjectAdminMember(Project project, User projectAdminUser, User createdByUser) {
		return projectMemberRepository.findByProjectAndUser(project, projectAdminUser)
			.map(projectMember -> {
				projectMember.assignProjectAdminRole();
				return projectMember;
			})
			.orElseGet(() -> createProjectAdminMember(project, projectAdminUser, createdByUser));
	}

	private ProjectMember findProjectAdminMember(Project project) {
		return projectMemberRepository.findByProjectAndUser(project, project.getProjectAdminUser())
			.orElse(null);
	}

	private User getCurrentUserEntity(AuthenticatedUser currentUser) {
		if (currentUser == null) {
			throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "인증 정보가 없습니다.");
		}

		return getUserEntity(currentUser.userId());
	}

	private User getUserEntity(Long userId) {
		return userRepository.findById(userId)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "사용자를 찾을 수 없습니다."));
	}

	private User getProjectAdminUser(String employeeNumber, String name) {
		return userRepository.findByEmployeeNumberAndName(employeeNumber, name)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "프로젝트 담당자를 찾을 수 없습니다."));
	}

	private void validateProjectAdminRequest(ProjectUpdateRequest request) {
		if (request.getAdminEmployeeNumber() == null || request.getAdminName() == null) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "프로젝트 담당자 사번과 이름을 모두 입력해야 합니다.");
		}
	}

	private void validateProjectUpdater(Project project, User user) {
		if (SystemRole.SUPER_ADMIN.equals(user.getSystemRole())) {
			return;
		}

		validateProjectAdmin(project, user);
	}

	private void validateProjectAdmin(Project project, User user) {
		ProjectMember projectMember = projectMemberRepository.findByProjectAndUser(project, user)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.FORBIDDEN, "프로젝트 ADMIN 권한이 필요합니다."));

		if (!ProjectRole.ADMIN.equals(projectMember.getProjectRole())
			|| !ProjectMemberStatus.IN_PROGRESS.equals(projectMember.getStatus())) {
			throw new ResponseStatusException(HttpStatus.FORBIDDEN, "프로젝트 ADMIN 권한이 필요합니다.");
		}
	}

	private void validateSuperAdmin(User user) {
		if (!SystemRole.SUPER_ADMIN.equals(user.getSystemRole())) {
			throw new ResponseStatusException(HttpStatus.FORBIDDEN, "SUPER_ADMIN 권한이 필요합니다.");
		}
	}

	private void validateActiveUser(User user, String message) {
		if (!UserStatus.ACTIVE.equals(user.getStatus())) {
			throw new ResponseStatusException(HttpStatus.CONFLICT, message);
		}
	}

	private Pageable createPageable(int page, int size) {
		return PageRequest.of(Math.max(page, 0), Math.max(size, 1));
	}
}
