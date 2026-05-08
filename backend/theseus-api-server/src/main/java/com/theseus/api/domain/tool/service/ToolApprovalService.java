package com.theseus.api.domain.tool.service;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.entity.ChatMessageContentType;
import com.theseus.api.domain.chat.entity.ChatMessageType;
import com.theseus.api.domain.chat.service.ChatMessageService;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.tool.dto.request.ToolApprovalApproveRequest;
import com.theseus.api.domain.tool.dto.request.ToolApprovalRejectRequest;
import com.theseus.api.domain.tool.dto.response.ToolApprovalResponse;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolApproval;
import com.theseus.api.domain.tool.entity.ToolApprovalStatus;
import com.theseus.api.domain.tool.repository.ToolApprovalRepository;
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.util.List;
import java.util.Objects;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ToolApprovalService {

	private final ToolApprovalRepository toolApprovalRepository;
	private final ToolRepository toolRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final UserRepository userRepository;
	private final ChatMessageService chatMessageService;

	/**
	 * 승인 권한을 가진 프로젝트 멤버가 Tool 승인 요청 목록을 조회합니다.
	 */
	public Page<ToolApprovalResponse> getToolApprovals(
		AuthenticatedUser currentUser,
		Long projectId,
		ToolApprovalStatus approvalStatus,
		int page,
		int size
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember reviewer = getActiveProjectMember(project, user);
		validateToolReviewer(reviewer);

		Pageable pageable = createPageable(page, size);
		Page<ToolApproval> toolApprovals = approvalStatus == null
			? toolApprovalRepository.findByProject(project, pageable)
			: toolApprovalRepository.findByProjectAndApprovalStatus(project, approvalStatus, pageable);

		return toolApprovals
			.map(ToolApprovalResponse::createFrom);
	}

	/**
	 * 승인 권한을 검증하고 Tool 승인 요청 상세 정보를 조회합니다.
	 */
	public ToolApprovalResponse getToolApproval(
		AuthenticatedUser currentUser,
		Long projectId,
		Long toolApprovalId
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember reviewer = getActiveProjectMember(project, user);
		validateToolReviewer(reviewer);

		ToolApproval toolApproval = toolApprovalRepository.findByIdAndToolProject(toolApprovalId, project)
			.orElseThrow(() -> BusinessException.of(ErrorCode.TOOL_APPROVAL_NOT_FOUND));

		return ToolApprovalResponse.createFrom(toolApproval);
	}

	/**
	 * Tool 생성자가 REVIEW 단계의 Draft Tool에 대해 승인 요청을 등록합니다.
	 */
	@Transactional
	public ToolApprovalResponse requestToolApproval(
		AuthenticatedUser currentUser,
		Long projectId,
		Long toolId
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);
		Tool tool = getToolForUpdate(project, toolId);

		validateToolCreator(tool, projectMember);
		validateRequestableTool(tool);

		ToolApproval toolApproval = toolApprovalRepository.save(ToolApproval.builder()
			.tool(tool)
			.requestNumber(getNextRequestNumber(tool))
			.requestedByProjectMember(projectMember)
			.build());
		tool.requestApproval();
		chatMessageService.saveUserToolMessage(
			tool.getChatSession(),
			tool,
			ChatMessageType.TOOL_APPROVAL_REQUEST,
			ChatMessageContentType.JSON,
			createToolApprovalRequestMessageContent(toolApproval)
		);

		return ToolApprovalResponse.createFrom(toolApproval);
	}

	/**
	 * 승인 담당자가 대기 중인 Tool 승인 요청을 승인 처리합니다.
	 */
	@Transactional
	public ToolApprovalResponse approveToolApproval(
		AuthenticatedUser currentUser,
		Long projectId,
		Long toolApprovalId,
		ToolApprovalApproveRequest request
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember reviewer = getActiveProjectMember(project, user);
		validateToolReviewer(reviewer);
		ToolApproval toolApproval = getToolApprovalForUpdate(project, toolApprovalId);
		Tool tool = toolApproval.getTool();

		validateReviewableToolApproval(toolApproval);
		validatePendingTool(tool);

		toolApproval.approve(reviewer, request.getReviewFeedback());
		tool.approve(request.getToolGrade());

		return ToolApprovalResponse.createFrom(toolApproval);
	}

	/**
	 * 승인 담당자가 대기 중인 Tool 승인 요청을 반려 처리합니다.
	 */
	@Transactional
	public ToolApprovalResponse rejectToolApproval(
		AuthenticatedUser currentUser,
		Long projectId,
		Long toolApprovalId,
		ToolApprovalRejectRequest request
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember reviewer = getActiveProjectMember(project, user);
		validateToolReviewer(reviewer);
		ToolApproval toolApproval = getToolApprovalForUpdate(project, toolApprovalId);
		Tool tool = toolApproval.getTool();

		validateReviewableToolApproval(toolApproval);
		validatePendingTool(tool);

		toolApproval.reject(reviewer, request.getReviewFeedback());
		tool.reject();

		return ToolApprovalResponse.createFrom(toolApproval);
	}

	private Integer getNextRequestNumber(Tool tool) {
		List<ToolApproval> toolApprovals = toolApprovalRepository.findByToolOrderByRequestNumberDescForUpdate(tool);

		return toolApprovals.stream()
			.findFirst()
			.map(toolApproval -> toolApproval.getRequestNumber() + 1)
			.orElse(1);
	}

	private String createToolApprovalRequestMessageContent(ToolApproval toolApproval) {
		return """
			{"toolApprovalId":%d,"toolId":%d,"requestNumber":%d,"approvalStatus":"%s"}
			""".formatted(
			toolApproval.getId(),
			toolApproval.getTool().getId(),
			toolApproval.getRequestNumber(),
			toolApproval.getApprovalStatus()
		).trim();
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

	private Tool getToolForUpdate(Project project, Long toolId) {
		return toolRepository.findByIdAndProjectForUpdate(toolId, project)
			.orElseThrow(() -> BusinessException.of(ErrorCode.TOOL_NOT_FOUND));
	}

	private ToolApproval getToolApprovalForUpdate(Project project, Long toolApprovalId) {
		return toolApprovalRepository.findByIdAndToolProjectForUpdate(toolApprovalId, project)
			.orElseThrow(() -> BusinessException.of(ErrorCode.TOOL_APPROVAL_NOT_FOUND));
	}

	private void validateToolCreator(Tool tool, ProjectMember projectMember) {
		if (!Objects.equals(tool.getCreatedByProjectMember().getId(), projectMember.getId())) {
			throw BusinessException.of(ErrorCode.TOOL_APPROVAL_CREATOR_REQUIRED);
		}
	}

	private void validateRequestableTool(Tool tool) {
		if (!tool.canRequestApproval()) {
			throw BusinessException.of(ErrorCode.TOOL_APPROVAL_REVIEW_PHASE_REQUIRED);
		}
	}

	private void validateToolReviewer(ProjectMember projectMember) {
		if (!ProjectRole.ADMIN.equals(projectMember.getProjectRole())
			&& !ProjectRole.MANAGER.equals(projectMember.getProjectRole())) {
			throw BusinessException.of(ErrorCode.TOOL_APPROVAL_REVIEWER_REQUIRED);
		}
	}

	private void validateReviewableToolApproval(ToolApproval toolApproval) {
		if (!toolApproval.isPending()) {
			throw BusinessException.of(ErrorCode.TOOL_APPROVAL_ALREADY_REVIEWED);
		}
	}

	private void validatePendingTool(Tool tool) {
		if (!tool.isPending()) {
			throw BusinessException.of(ErrorCode.TOOL_APPROVAL_PENDING_TOOL_REQUIRED);
		}
	}

	private Pageable createPageable(int page, int size) {
		return PageRequest.of(Math.max(page, 0), Math.max(size, 1));
	}
}
