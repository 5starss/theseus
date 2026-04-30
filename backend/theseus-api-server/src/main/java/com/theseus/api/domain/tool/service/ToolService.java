package com.theseus.api.domain.tool.service;

import com.theseus.api.common.exception.CustomException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.tool.dto.response.ToolDetailResponse;
import com.theseus.api.domain.tool.dto.response.ToolSummaryResponse;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolStatus;
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.user.entity.User;
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
public class ToolService {

	private static final String ACCESSIBLE_SCOPE = "accessible";

	private final ToolRepository toolRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final UserRepository userRepository;

	public Page<ToolSummaryResponse> getTools(
		AuthenticatedUser currentUser,
		Long projectId,
		String scope,
		ToolStatus status,
		int page,
		int size
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);

		validateAccessibleScope(scope);
		validateApprovedStatus(status);
		validateToolUsePermission(projectMember);

		Pageable pageable = createPageable(page, size);
		return toolRepository.findAccessibleByProjectAndStatus(
				project,
				ToolStatus.APPROVED,
				projectMember.getAccessLevel(),
				pageable
			)
			.map(ToolSummaryResponse::createFrom);
	}

	public ToolDetailResponse getTool(
		AuthenticatedUser currentUser,
		Long projectId,
		Long toolId
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);
		validateToolUsePermission(projectMember);

		Tool tool = getToolEntity(project, toolId);
		validateApprovedStatus(tool.getStatus());
		validateAccessibleTool(projectMember, tool);

		return ToolDetailResponse.createFrom(tool);
	}

	private User getCurrentUserEntity(AuthenticatedUser currentUser) {
		if (currentUser == null) {
			throw new CustomException(ErrorCode.UNAUTHORIZED);
		}

		return userRepository.findById(currentUser.userId())
			.orElseThrow(() -> new CustomException(ErrorCode.USER_NOT_FOUND));
	}

	private Project getProjectEntity(Long projectId) {
		return projectRepository.findById(projectId)
			.orElseThrow(() -> new CustomException(ErrorCode.PROJECT_NOT_FOUND));
	}

	private ProjectMember getActiveProjectMember(Project project, User user) {
		ProjectMember projectMember = projectMemberRepository.findByProjectAndUser(project, user)
			.orElseThrow(() -> new CustomException(ErrorCode.PROJECT_MEMBER_PERMISSION_REQUIRED));

		if (!ProjectMemberStatus.IN_PROGRESS.equals(projectMember.getStatus())) {
			throw new CustomException(ErrorCode.ACTIVE_PROJECT_MEMBER_REQUIRED);
		}

		return projectMember;
	}

	private Tool getToolEntity(Project project, Long toolId) {
		return toolRepository.findByIdAndProjectAndStatusNot(toolId, project, ToolStatus.DELETED)
			.orElseThrow(() -> new CustomException(ErrorCode.TOOL_NOT_FOUND));
	}

	private void validateAccessibleScope(String scope) {
		if (!ACCESSIBLE_SCOPE.equals(scope)) {
			throw new CustomException(ErrorCode.UNSUPPORTED_TOOL_SCOPE);
		}
	}

	private void validateApprovedStatus(ToolStatus status) {
		if (!ToolStatus.APPROVED.equals(status)) {
			throw new CustomException(ErrorCode.APPROVED_TOOL_ONLY);
		}
	}

	private void validateToolUsePermission(ProjectMember projectMember) {
		if (!Boolean.TRUE.equals(projectMember.getCanUseTool())) {
			throw new CustomException(ErrorCode.TOOL_USE_PERMISSION_REQUIRED);
		}
	}

	private void validateAccessibleTool(ProjectMember projectMember, Tool tool) {
		if (!tool.isAccessibleWithAccessLevel(projectMember.getAccessLevel())) {
			throw new CustomException(ErrorCode.TOOL_ACCESS_LEVEL_REQUIRED);
		}
	}

	private Pageable createPageable(int page, int size) {
		return PageRequest.of(Math.max(page, 0), Math.max(size, 1));
	}
}
