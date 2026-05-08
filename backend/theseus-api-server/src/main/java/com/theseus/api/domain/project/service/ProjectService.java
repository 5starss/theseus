package com.theseus.api.domain.project.service;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
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
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ProjectService {

	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final UserRepository userRepository;

	/**
	 * 로그인 사용자가 참여 중인 활성 프로젝트 목록을 조회합니다.
	 */
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

	/**
	 * Super Admin이 프로젝트 목록을 상태 조건과 함께 조회합니다.
	 */
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

	/**
	 * 프로젝트 접근 권한을 검증하고 프로젝트 상세 정보를 조회합니다.
	 */
	public ProjectResponse getProject(AuthenticatedUser currentUser, Long projectId) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);

		validateProjectViewer(project, user);

		return ProjectResponse.createOf(project, findProjectAdminMember(project));
	}

	/**
	 * Super Admin이 프로젝트를 생성하고 지정한 담당자를 프로젝트 ADMIN으로 등록합니다.
	 */
	@Transactional
	public ProjectResponse createProject(AuthenticatedUser currentUser, ProjectCreateRequest request) {
		User createdByUser = getCurrentUserEntity(currentUser);
		validateSuperAdmin(createdByUser);

		User projectAdminUser = getProjectAdminUser(request.getAdminEmployeeNumber(), request.getAdminName());
		validateActiveUser(projectAdminUser);

		Project project = projectRepository.save(request.toEntity(createdByUser, projectAdminUser));
		ProjectMember adminMember = createProjectAdminMember(project, projectAdminUser, createdByUser);

		return ProjectResponse.createOf(project, adminMember);
	}

	/**
	 * 프로젝트 기본 정보를 수정하고 필요한 경우 대표 담당자를 변경합니다.
	 */
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
		validateActiveUser(projectAdminUser);
		project.updateProjectAdminUser(projectAdminUser);
		ProjectMember adminMember = ensureProjectAdminMember(project, projectAdminUser, user);

		return ProjectResponse.createOf(project, adminMember);
	}

	/**
	 * 프로젝트 ID로 프로젝트 엔티티를 조회합니다.
	 */
	public Project getProjectEntity(Long projectId) {
		return projectRepository.findById(projectId)
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_NOT_FOUND));
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
			throw BusinessException.of(ErrorCode.UNAUTHORIZED);
		}

		return getUserEntity(currentUser.userId());
	}

	private User getUserEntity(Long userId) {
		return userRepository.findById(userId)
			.orElseThrow(() -> BusinessException.of(ErrorCode.USER_NOT_FOUND));
	}

	private User getProjectAdminUser(String employeeNumber, String name) {
		return userRepository.findByEmployeeNumberAndName(employeeNumber, name)
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_ADMIN_USER_NOT_FOUND));
	}

	private void validateProjectAdminRequest(ProjectUpdateRequest request) {
		if (request.getAdminEmployeeNumber() == null || request.getAdminName() == null) {
			throw BusinessException.of(ErrorCode.PROJECT_ADMIN_REQUEST_REQUIRED);
		}
	}

	private void validateProjectUpdater(Project project, User user) {
		if (SystemRole.SUPER_ADMIN.equals(user.getSystemRole())) {
			return;
		}

		validateProjectAdmin(project, user);
	}

	private void validateProjectViewer(Project project, User user) {
		if (SystemRole.SUPER_ADMIN.equals(user.getSystemRole())) {
			return;
		}

		if (!ProjectStatus.ACTIVE.equals(project.getStatus())) {
			throw BusinessException.of(ErrorCode.ACTIVE_PROJECT_REQUIRED);
		}

		ProjectMember projectMember = projectMemberRepository.findByProjectAndUser(project, user)
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_MEMBER_PERMISSION_REQUIRED));

		if (!ProjectMemberStatus.IN_PROGRESS.equals(projectMember.getStatus())) {
			throw BusinessException.of(ErrorCode.ACTIVE_PROJECT_MEMBER_REQUIRED);
		}
	}

	private void validateProjectAdmin(Project project, User user) {
		ProjectMember projectMember = projectMemberRepository.findByProjectAndUser(project, user)
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_ADMIN_PERMISSION_REQUIRED));

		if (!ProjectRole.ADMIN.equals(projectMember.getProjectRole())
			|| !ProjectMemberStatus.IN_PROGRESS.equals(projectMember.getStatus())) {
			throw BusinessException.of(ErrorCode.PROJECT_ADMIN_PERMISSION_REQUIRED);
		}
	}

	private void validateSuperAdmin(User user) {
		if (!SystemRole.SUPER_ADMIN.equals(user.getSystemRole())) {
			throw BusinessException.of(ErrorCode.SUPER_ADMIN_PERMISSION_REQUIRED);
		}
	}

	private void validateActiveUser(User user) {
		if (!UserStatus.ACTIVE.equals(user.getStatus())) {
			throw BusinessException.of(ErrorCode.PROJECT_ADMIN_USER_ACTIVE_REQUIRED);
		}
	}

	private Pageable createPageable(int page, int size) {
		return PageRequest.of(Math.max(page, 0), Math.max(size, 1));
	}
}
