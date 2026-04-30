package com.theseus.api.domain.project.service;

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
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ProjectMemberService {

	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final UserRepository userRepository;

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

	public ProjectMemberResponse getMyProjectMember(AuthenticatedUser currentUser, Long projectId) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getProjectMember(project, user);

		return ProjectMemberResponse.createOf(projectMember, isProjectAdminUser(projectMember));
	}

	@Transactional
	public ProjectMemberResponse createProjectMember(
		AuthenticatedUser currentUser,
		Long projectId,
		ProjectMemberCreateRequest request
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		validateProjectAdmin(project, user);
		User targetUser = getUserEntity(request.getUserId());
		validateActiveUser(targetUser);

		if (projectMemberRepository.existsByProjectAndUser(project, targetUser)) {
			throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 등록된 프로젝트 멤버입니다.");
		}

		ProjectMember projectMember = projectMemberRepository.save(request.toEntity(project, targetUser, user));

		return ProjectMemberResponse.createOf(projectMember, isProjectAdminUser(projectMember));
	}

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
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "프로젝트를 찾을 수 없습니다."));
	}

	private ProjectMember getProjectMemberEntity(Project project, Long projectMemberId) {
		return projectMemberRepository.findByProjectAndId(project, projectMemberId)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "프로젝트 멤버를 찾을 수 없습니다."));
	}

	private ProjectMember getProjectMember(Project project, User user) {
		return projectMemberRepository.findByProjectAndUser(project, user)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "프로젝트 멤버를 찾을 수 없습니다."));
	}

	private User getUserEntity(Long userId) {
		return userRepository.findById(userId)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "사용자를 찾을 수 없습니다."));
	}

	private User getCurrentUserEntity(AuthenticatedUser currentUser) {
		if (currentUser == null) {
			throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "인증 정보가 없습니다.");
		}

		return getUserEntity(currentUser.userId());
	}

	private void validateProjectMember(Project project, User user) {
		ProjectMember projectMember = projectMemberRepository.findByProjectAndUser(project, user)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.FORBIDDEN, "프로젝트 멤버 권한이 필요합니다."));

		if (!ProjectMemberStatus.IN_PROGRESS.equals(projectMember.getStatus())) {
			throw new ResponseStatusException(HttpStatus.FORBIDDEN, "프로젝트 멤버 권한이 필요합니다.");
		}
	}

	private void validateProjectAdmin(Project project, User user) {
		ProjectMember projectMember = projectMemberRepository.findByProjectAndUser(project, user)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.FORBIDDEN, "프로젝트 ADMIN 권한이 필요합니다."));

		if (!ProjectRole.ADMIN.equals(projectMember.getProjectRole())
			|| !ProjectMemberStatus.IN_PROGRESS.equals(projectMember.getStatus())) {
			throw new ResponseStatusException(HttpStatus.FORBIDDEN, "프로젝트 ADMIN 권한이 필요합니다.");
		}
	}

	private void validateProjectAdminUserUpdate(ProjectMember projectMember, ProjectMemberUpdateRequest request) {
		if (!isProjectAdminUser(projectMember)) {
			return;
		}

		ProjectRole nextRole = request.getProjectRole() == null ? projectMember.getProjectRole() : request.getProjectRole();
		ProjectMemberStatus nextStatus = request.getStatus() == null ? projectMember.getStatus() : request.getStatus();

		if (!ProjectRole.ADMIN.equals(nextRole) || !ProjectMemberStatus.IN_PROGRESS.equals(nextStatus)) {
			throw new ResponseStatusException(HttpStatus.CONFLICT, "프로젝트 담당자는 ADMIN/진행중 상태를 유지해야 합니다.");
		}
	}

	private void validateActiveUser(User user) {
		if (!UserStatus.ACTIVE.equals(user.getStatus())) {
			throw new ResponseStatusException(HttpStatus.CONFLICT, "활성 사용자만 프로젝트 멤버로 등록할 수 있습니다.");
		}
	}

	private boolean isProjectAdminUser(ProjectMember projectMember) {
		return projectMember.getProject().getProjectAdminUser().getId().equals(projectMember.getUser().getId());
	}
}
