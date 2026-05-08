package com.theseus.api.domain.project.service;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.project.dto.request.ProjectMemberCreateRequest;
import com.theseus.api.domain.project.dto.request.ProjectMemberUpdateRequest;
import com.theseus.api.domain.project.dto.response.ProjectMemberResponse;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.entity.UserStatus;
import com.theseus.api.domain.user.repository.UserRepository;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ProjectMemberService {

	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final UserRepository userRepository;

	/**
	 * 프로젝트 멤버 권한을 확인하고 멤버 목록을 상태 조건과 함께 조회합니다.
	 */
	public List<ProjectMemberResponse> getProjectMembers(
		AuthenticatedUser currentUser,
		Long projectId,
		ProjectMemberStatus status
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		validateProjectMember(project, user);

		List<ProjectMember> projectMembers = status == null
			? projectMemberRepository.findByProject(project)
			: projectMemberRepository.findByProjectAndStatus(project, status);

		return projectMembers.stream()
			.map(projectMember -> ProjectMemberResponse.createOf(projectMember, isProjectAdminUser(projectMember)))
			.toList();
	}

	/**
	 * 로그인 사용자의 프로젝트 멤버 정보를 조회합니다.
	 */
	public ProjectMemberResponse getMyProjectMember(AuthenticatedUser currentUser, Long projectId) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getProjectMember(project, user);

		return ProjectMemberResponse.createOf(projectMember, isProjectAdminUser(projectMember));
	}

	/**
	 * 프로젝트 ADMIN이 사번 기준으로 새 프로젝트 멤버를 등록합니다.
	 */
	@Transactional
	public ProjectMemberResponse createProjectMember(
		AuthenticatedUser currentUser,
		Long projectId,
		ProjectMemberCreateRequest request
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		validateProjectAdmin(project, user);
		User targetUser = getUserEntityByEmployeeNumber(request.getEmployeeNumber());
		validateActiveUser(targetUser);

		if (projectMemberRepository.existsByProjectAndUser(project, targetUser)) {
			throw BusinessException.of(ErrorCode.DUPLICATE_PROJECT_MEMBER);
		}

		ProjectMember projectMember = projectMemberRepository.save(request.toEntity(project, targetUser, user));

		return ProjectMemberResponse.createOf(projectMember, isProjectAdminUser(projectMember));
	}

	/**
	 * 프로젝트 ADMIN이 멤버 권한과 상태를 수정합니다.
	 */
	@Transactional
	public ProjectMemberResponse updateProjectMember(
		AuthenticatedUser currentUser,
		Long projectId,
		Long projectMemberId,
		ProjectMemberUpdateRequest request
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		validateProjectAdmin(project, user);
		ProjectMember projectMember = getProjectMemberEntity(project, projectMemberId);

		validateProjectAdminUserUpdate(projectMember, request);
		projectMember.update(
			request.getProjectRole(),
			request.getAccessLevel(),
			request.getCanCreateTool(),
			request.getCanUseTool(),
			request.getCanUpdateTool(),
			request.getCanDeleteTool(),
			request.getStatus()
		);

		return ProjectMemberResponse.createOf(projectMember, isProjectAdminUser(projectMember));
	}

	private Project getProjectEntity(Long projectId) {
		return projectRepository.findById(projectId)
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_NOT_FOUND));
	}

	private ProjectMember getProjectMemberEntity(Project project, Long projectMemberId) {
		return projectMemberRepository.findByProjectAndId(project, projectMemberId)
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_MEMBER_NOT_FOUND));
	}

	private ProjectMember getProjectMember(Project project, User user) {
		return projectMemberRepository.findByProjectAndUser(project, user)
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_MEMBER_NOT_FOUND));
	}

	private User getUserEntity(Long userId) {
		return userRepository.findById(userId)
			.orElseThrow(() -> BusinessException.of(ErrorCode.USER_NOT_FOUND));
	}

	private User getUserEntityByEmployeeNumber(String employeeNumber) {
		return userRepository.findByEmployeeNumber(employeeNumber)
			.orElseThrow(() -> BusinessException.of(ErrorCode.USER_NOT_FOUND));
	}

	private User getCurrentUserEntity(AuthenticatedUser currentUser) {
		if (currentUser == null) {
			throw BusinessException.of(ErrorCode.UNAUTHORIZED);
		}

		return getUserEntity(currentUser.userId());
	}

	private void validateProjectMember(Project project, User user) {
		ProjectMember projectMember = projectMemberRepository.findByProjectAndUser(project, user)
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_MEMBER_PERMISSION_REQUIRED));

		if (!ProjectMemberStatus.IN_PROGRESS.equals(projectMember.getStatus())) {
			throw BusinessException.of(ErrorCode.PROJECT_MEMBER_PERMISSION_REQUIRED);
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

	private void validateProjectAdminUserUpdate(ProjectMember projectMember, ProjectMemberUpdateRequest request) {
		if (!isProjectAdminUser(projectMember)) {
			return;
		}

		ProjectRole nextRole = request.getProjectRole() == null ? projectMember.getProjectRole() : request.getProjectRole();
		ProjectMemberStatus nextStatus = request.getStatus() == null ? projectMember.getStatus() : request.getStatus();

		if (!ProjectRole.ADMIN.equals(nextRole) || !ProjectMemberStatus.IN_PROGRESS.equals(nextStatus)) {
			throw BusinessException.of(ErrorCode.PROJECT_ADMIN_MEMBER_REQUIRED);
		}
	}

	private void validateActiveUser(User user) {
		if (!UserStatus.ACTIVE.equals(user.getStatus())) {
			throw BusinessException.of(ErrorCode.PROJECT_MEMBER_ACTIVE_USER_REQUIRED);
		}
	}

	private boolean isProjectAdminUser(ProjectMember projectMember) {
		return projectMember.getProject().getProjectAdminUser().getId().equals(projectMember.getUser().getId());
	}
}
