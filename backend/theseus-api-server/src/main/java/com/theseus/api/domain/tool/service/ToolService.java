package com.theseus.api.domain.tool.service;

import com.theseus.api.common.exception.BusinessException;
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

	/**
	 * 프로젝트 멤버가 사용할 수 있는 승인 완료 Tool 목록을 조회합니다.
	 */
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

	/**
	 * 접근 권한과 등급 조건을 검증하고 Tool 상세 정보를 조회합니다.
	 */
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

	/**
	 * Tool을 논리 삭제 처리합니다.
	 */
	@Transactional
	public void deleteTool(AuthenticatedUser currentUser, Long projectId, Long toolId) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);
		validateToolUsePermission(projectMember);

		Tool tool = getToolEntity(project, toolId);
		tool.delete();
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

	private Tool getToolEntity(Project project, Long toolId) {
		return toolRepository.findByIdAndProjectAndStatusNot(toolId, project, ToolStatus.DELETED)
			.orElseThrow(() -> BusinessException.of(ErrorCode.TOOL_NOT_FOUND));
	}

	private void validateAccessibleScope(String scope) {
		if (!ACCESSIBLE_SCOPE.equals(scope)) {
			throw BusinessException.of(ErrorCode.UNSUPPORTED_TOOL_SCOPE);
		}
	}

	private void validateApprovedStatus(ToolStatus status) {
		if (!ToolStatus.APPROVED.equals(status)) {
			throw BusinessException.of(ErrorCode.APPROVED_TOOL_ONLY);
		}
	}

	private void validateToolUsePermission(ProjectMember projectMember) {
		if (!Boolean.TRUE.equals(projectMember.getCanUseTool())) {
			throw BusinessException.of(ErrorCode.TOOL_USE_PERMISSION_REQUIRED);
		}
	}

	private void validateAccessibleTool(ProjectMember projectMember, Tool tool) {
		if (!tool.isAccessibleWithAccessLevel(projectMember.getAccessLevel())) {
			throw BusinessException.of(ErrorCode.TOOL_ACCESS_LEVEL_REQUIRED);
		}
	}

	private Pageable createPageable(int page, int size) {
		return PageRequest.of(Math.max(page, 0), Math.max(size, 1));
	}
}
