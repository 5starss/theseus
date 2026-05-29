package com.theseus.api.domain.tool.service;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.tool.dto.response.ToolUsageListResponse;
import com.theseus.api.domain.tool.dto.response.ToolUsageResponse;
import com.theseus.api.domain.tool.entity.ToolUsageStatus;
import com.theseus.api.domain.tool.repository.ToolUsageLogRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ToolUsageService {

	private final ToolUsageLogRepository toolUsageLogRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final UserRepository userRepository;

	public ToolUsageListResponse getToolUsages(
		AuthenticatedUser currentUser,
		Long projectId,
		int page,
		int size,
		ToolUsageStatus status
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);
		validateProjectAdmin(projectMember);

		Pageable pageable = PageRequest.of(
			Math.max(page, 0),
			Math.max(size, 1),
			Sort.by(Sort.Direction.DESC, "usedAt")
		);
		// TODO(S14P31A308-483): Tool execution completed/failed 이벤트 수신 지점에서 ToolUsageLog 저장을 연결합니다.
		return ToolUsageListResponse.createFrom(
			findToolUsageLogs(project, status, pageable)
				.map(ToolUsageResponse::createFrom)
		);
	}

	private org.springframework.data.domain.Page<com.theseus.api.domain.tool.entity.ToolUsageLog> findToolUsageLogs(
		Project project,
		ToolUsageStatus status,
		Pageable pageable
	) {
		if (status == null) {
			return toolUsageLogRepository.findByProjectOrderByUsedAtDesc(project, pageable);
		}

		return toolUsageLogRepository.findByProjectAndStatusOrderByUsedAtDesc(project, status, pageable);
	}

	private User getCurrentUserEntity(AuthenticatedUser currentUser) {
		if (currentUser == null) {
			throw BusinessException.of(ErrorCode.UNAUTHORIZED);
		}

		return userRepository.findById(currentUser.userId())
			.orElseThrow(() -> BusinessException.of(ErrorCode.USER_NOT_FOUND));
	}

	private Project getProjectEntity(Long projectId) {
		return projectRepository.findById(projectId)
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_NOT_FOUND));
	}

	private ProjectMember getActiveProjectMember(Project project, User user) {
		ProjectMember projectMember = projectMemberRepository.findByProjectAndUser(project, user)
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_MEMBER_PERMISSION_REQUIRED));

		if (!ProjectMemberStatus.IN_PROGRESS.equals(projectMember.getStatus())) {
			throw BusinessException.of(ErrorCode.ACTIVE_PROJECT_MEMBER_REQUIRED);
		}

		return projectMember;
	}

	private void validateProjectAdmin(ProjectMember projectMember) {
		if (!ProjectRole.ADMIN.equals(projectMember.getProjectRole())) {
			throw BusinessException.of(ErrorCode.PROJECT_ADMIN_PERMISSION_REQUIRED);
		}
	}

}
