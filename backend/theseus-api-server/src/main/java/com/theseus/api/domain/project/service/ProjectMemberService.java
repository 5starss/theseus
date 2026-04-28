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
public class ProjectMemberService {

	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final UserRepository userRepository;

	public List<ProjectMemberResponse> getProjectMembers(Long projectId) {
		User currentUser = getCurrentUserEntity();
		Project project = getProjectEntity(projectId);
		validateProjectAdmin(project, currentUser);

		return projectMemberRepository.findByProject(project).stream()
			.map(ProjectMemberResponse::createFrom)
			.toList();
	}

	public ProjectMemberResponse getProjectMember(Long projectMemberId) {
		User currentUser = getCurrentUserEntity();
		ProjectMember projectMember = getProjectMemberEntity(projectMemberId);
		validateProjectAdmin(projectMember.getProject(), currentUser);

		return ProjectMemberResponse.createFrom(projectMember);
	}

	@Transactional
	public ProjectMemberResponse createProjectMember(Long projectId, ProjectMemberCreateRequest request) {
		User currentUser = getCurrentUserEntity();
		Project project = getProjectEntity(projectId);
		validateProjectAdmin(project, currentUser);
		User targetUser = getUserEntity(request.getUserId());

		if (projectMemberRepository.existsByProjectAndUser(project, targetUser)) {
			throw new ResponseStatusException(HttpStatus.CONFLICT, "이미 등록된 프로젝트 멤버입니다.");
		}

		ProjectMember projectMember = projectMemberRepository.save(request.toEntity(project, targetUser, currentUser));

		return ProjectMemberResponse.createFrom(projectMember);
	}

	@Transactional
	public ProjectMemberResponse updateProjectMember(Long projectMemberId, ProjectMemberUpdateRequest request) {
		User currentUser = getCurrentUserEntity();
		ProjectMember projectMember = getProjectMemberEntity(projectMemberId);
		validateProjectAdmin(projectMember.getProject(), currentUser);
		ProjectMemberStatus status = request.getStatus() == null ? projectMember.getStatus() : request.getStatus();

		projectMember.update(
			request.getProjectRole(),
			request.getAccessLevel(),
			request.getCanCreateTool(),
			request.getCanUseTool(),
			request.getCanUpdateTool(),
			request.getCanDeleteTool(),
			status
		);

		return ProjectMemberResponse.createFrom(projectMember);
	}

	@Transactional
	public ProjectMemberResponse deleteProjectMember(Long projectMemberId) {
		User currentUser = getCurrentUserEntity();
		ProjectMember projectMember = getProjectMemberEntity(projectMemberId);
		validateProjectAdmin(projectMember.getProject(), currentUser);

		projectMember.complete();

		return ProjectMemberResponse.createFrom(projectMember);
	}

	private Project getProjectEntity(Long projectId) {
		return projectRepository.findById(projectId)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "프로젝트를 찾을 수 없습니다."));
	}

	private ProjectMember getProjectMemberEntity(Long projectMemberId) {
		return projectMemberRepository.findById(projectMemberId)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "프로젝트 멤버를 찾을 수 없습니다."));
	}

	private User getUserEntity(Long userId) {
		return userRepository.findById(userId)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "사용자를 찾을 수 없습니다."));
	}

	private User getCurrentUserEntity() {
		Authentication authentication = SecurityContextHolder.getContext().getAuthentication();

		if (authentication == null || !(authentication.getPrincipal() instanceof AuthenticatedUser authenticatedUser)) {
			throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "인증 정보가 없습니다.");
		}

		return getUserEntity(authenticatedUser.userId());
	}

	private void validateProjectAdmin(Project project, User user) {
		ProjectMember projectMember = projectMemberRepository.findByProjectAndUser(project, user)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.FORBIDDEN, "프로젝트 ADMIN 권한이 필요합니다."));

		if (!ProjectRole.ADMIN.equals(projectMember.getProjectRole())
			|| !ProjectMemberStatus.IN_PROGRESS.equals(projectMember.getStatus())) {
			throw new ResponseStatusException(HttpStatus.FORBIDDEN, "프로젝트 ADMIN 권한이 필요합니다.");
		}
	}
}
