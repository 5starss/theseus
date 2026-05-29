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
import com.theseus.api.domain.tool.entity.ToolUsageLog;
import com.theseus.api.domain.tool.repository.ToolUsageLogRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
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
		int size
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);
		validateProjectAdmin(projectMember);

		// TODO(S14P31A308-483): Tool execution completed/failed 이벤트 수신 지점에서 ToolUsageLog 저장을 연결합니다.
		List<ProjectMember> projectMembers = projectMemberRepository.findByProject(project)
			.stream()
			.sorted(Comparator.comparing(member -> member.getUser().getName()))
			.toList();
		Map<Long, List<ToolUsageLog>> usageLogsByProjectMemberId = toolUsageLogRepository
			.findByProjectOrderByUsedAtDesc(project)
			.stream()
			.collect(Collectors.groupingBy(usageLog -> usageLog.getUsedByProjectMember().getId()));

		int normalizedPage = Math.max(page, 0);
		int normalizedSize = Math.max(size, 1);
		int fromIndex = Math.min(normalizedPage * normalizedSize, projectMembers.size());
		int toIndex = Math.min(fromIndex + normalizedSize, projectMembers.size());

		List<ToolUsageResponse> items = projectMembers.subList(fromIndex, toIndex)
			.stream()
			.map(member -> ToolUsageResponse.createFrom(
				member,
				usageLogsByProjectMemberId.getOrDefault(member.getId(), Collections.emptyList())
			))
			.toList();

		return ToolUsageListResponse.createFrom(items, normalizedPage, normalizedSize, projectMembers.size());
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
