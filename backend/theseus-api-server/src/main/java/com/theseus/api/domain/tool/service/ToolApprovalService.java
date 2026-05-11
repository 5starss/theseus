package com.theseus.api.domain.tool.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
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
import com.theseus.api.domain.tool.entity.ToolPlan;
import com.theseus.api.domain.tool.entity.ToolPlanGroup;
import com.theseus.api.domain.tool.entity.ToolPlanGroupStatus;
import com.theseus.api.domain.tool.entity.ToolPlanMode;
import com.theseus.api.domain.tool.entity.ToolPlanRun;
import com.theseus.api.domain.tool.entity.ToolPlanRunRequestType;
import com.theseus.api.domain.tool.entity.ToolPlanRunStatus;
import com.theseus.api.domain.tool.entity.ToolPlanStatus;
import com.theseus.api.domain.tool.repository.ToolApprovalRepository;
import com.theseus.api.domain.tool.repository.ToolPlanRepository;
import com.theseus.api.domain.tool.repository.ToolPlanRunRepository;
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.toolgeneration.event.ToolBuildApprovedPlanPayload;
import com.theseus.api.domain.toolgeneration.event.ToolBuildKafkaPublishEvent;
import com.theseus.api.domain.toolgeneration.event.ToolBuildRequestEvent;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Objects;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ToolApprovalService {

	private static final String TOOL_BUILD_REQUESTED = "TOOL_BUILD_REQUESTED";

	private final ToolApprovalRepository toolApprovalRepository;
	private final ToolRepository toolRepository;
	private final ToolPlanRepository toolPlanRepository;
	private final ToolPlanRunRepository toolPlanRunRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final UserRepository userRepository;
	private final ChatMessageService chatMessageService;
	private final ApplicationEventPublisher eventPublisher;
	private final ObjectMapper objectMapper;

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
	 * REVIEW 상태의 ToolPlan을 승인 요청 대상으로 등록합니다.
	 */
	@Transactional
	public ToolApprovalResponse requestToolPlanApproval(
		AuthenticatedUser currentUser,
		Long projectId,
		Long toolPlanId
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);
		ToolPlan toolPlan = getToolPlanForUpdate(project, toolPlanId);

		validateToolPlanCreator(toolPlan, projectMember);
		validateRequestableToolPlan(toolPlan);

		ToolApproval toolApproval = toolApprovalRepository.save(ToolApproval.builder()
			.toolPlan(toolPlan)
			.requestNumber(getNextRequestNumber(toolPlan))
			.requestedByProjectMember(projectMember)
			.build());
		toolPlan.requestApproval();
		toolPlan.getPlanGroup().markPending(toolPlan);
		chatMessageService.saveUserToolPlanMessage(
			toolPlan.getChatSession(),
			toolPlan,
			ChatMessageType.TOOL_APPROVAL_REQUEST,
			ChatMessageContentType.JSON,
			createToolPlanApprovalRequestMessageContent(toolApproval)
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
		ToolPlan toolPlan = toolApproval.getToolPlan();

		validateReviewableToolApproval(toolApproval);
		if (toolPlan != null) {
			approveToolPlanApproval(toolApproval, toolPlan, reviewer, request);
			return ToolApprovalResponse.createFrom(toolApproval);
		}

		validatePendingTool(tool);
		validateToolGrade(request);

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
		ToolPlan toolPlan = toolApproval.getToolPlan();

		validateReviewableToolApproval(toolApproval);
		if (toolPlan != null) {
			rejectToolPlanApproval(toolApproval, toolPlan, reviewer, request);
			return ToolApprovalResponse.createFrom(toolApproval);
		}

		validatePendingTool(tool);

		toolApproval.reject(reviewer, request.getReviewFeedback());
		tool.reject();

		return ToolApprovalResponse.createFrom(toolApproval);
	}

	/**
	 * Tool build Kafka 발행 실패를 별도 트랜잭션으로 기록합니다.
	 */
	@Transactional(propagation = Propagation.REQUIRES_NEW)
	public void markBuildRunPublishFailed(String runId, Throwable exception) {
		toolPlanRunRepository.findByRunId(runId).ifPresentOrElse(
			toolPlanRun -> {
				if (toolPlanRun.isFinished()) {
					return;
				}

				toolPlanRun.fail(
					ErrorCode.TOOL_BUILD_KAFKA_PUBLISH_FAILED.getCode(),
					resolveErrorMessage(exception),
					LocalDateTime.now()
				);
			},
			() -> log.warn(">>>> ToolPlanRun을 찾을 수 없어 Tool build 발행 실패를 기록하지 못했습니다. runId={}", runId)
		);
	}

	private Integer getNextRequestNumber(Tool tool) {
		List<ToolApproval> toolApprovals = toolApprovalRepository.findByToolOrderByRequestNumberDescForUpdate(tool);

		return toolApprovals.stream()
			.findFirst()
			.map(toolApproval -> toolApproval.getRequestNumber() + 1)
			.orElse(1);
	}

	private Integer getNextRequestNumber(ToolPlan toolPlan) {
		List<ToolApproval> toolApprovals = toolApprovalRepository.findByToolPlanOrderByRequestNumberDescForUpdate(toolPlan);

		return toolApprovals.stream()
			.findFirst()
			.map(toolApproval -> toolApproval.getRequestNumber() + 1)
			.orElse(1);
	}

	private void approveToolPlanApproval(
		ToolApproval toolApproval,
		ToolPlan toolPlan,
		ProjectMember reviewer,
		ToolApprovalApproveRequest request
	) {
		validatePendingToolPlan(toolPlan);

		toolApproval.approve(reviewer, request.getReviewFeedback());
		toolPlan.approve();
		toolPlan.getPlanGroup().approve(toolPlan);

		ToolPlanRun buildRun = createBuildToolPlanRun(toolPlan, reviewer);
		ToolBuildRequestEvent requestEvent = createBuildRequestEvent(buildRun, toolPlan, reviewer);
		buildRun.attachRequestPayload(writeAsJson(requestEvent), null);
		eventPublisher.publishEvent(new ToolBuildKafkaPublishEvent(buildRun.getRunId(), requestEvent));
	}

	private void rejectToolPlanApproval(
		ToolApproval toolApproval,
		ToolPlan toolPlan,
		ProjectMember reviewer,
		ToolApprovalRejectRequest request
	) {
		validatePendingToolPlan(toolPlan);

		toolApproval.reject(reviewer, request.getReviewFeedback());
		toolPlan.reject();
		toolPlan.getPlanGroup().reject();
		chatMessageService.saveSystemToolPlanMessage(
			toolPlan.getChatSession(),
			toolPlan,
			createToolPlanRejectionNotice(toolApproval)
		);
	}

	private ToolPlanRun createBuildToolPlanRun(ToolPlan toolPlan, ProjectMember reviewer) {
		return toolPlanRunRepository.save(ToolPlanRun.builder()
			.runId(createRunId())
			.project(toolPlan.getProject())
			.chatSession(toolPlan.getChatSession())
			.requestType(ToolPlanRunRequestType.BUILD_TOOL)
			.mode(ToolPlanMode.PLAN)
			.status(ToolPlanRunStatus.REQUESTED)
			.requestedByProjectMember(reviewer)
			.baseToolPlan(toolPlan)
			.planGroup(toolPlan.getPlanGroup())
			.requestedAt(LocalDateTime.now())
			.build());
	}

	private ToolBuildRequestEvent createBuildRequestEvent(
		ToolPlanRun buildRun,
		ToolPlan toolPlan,
		ProjectMember reviewer
	) {
		return new ToolBuildRequestEvent(
			TOOL_BUILD_REQUESTED,
			buildRun.getRunId(),
			toolPlan.getProject().getId(),
			toolPlan.getChatSession().getId(),
			toolPlan.getId(),
			toolPlan.getPlanGroup().getId(),
			reviewer.getId(),
			createApprovedPlanPayload(toolPlan),
			buildRun.getRequestedAt()
		);
	}

	private ToolBuildApprovedPlanPayload createApprovedPlanPayload(ToolPlan toolPlan) {
		return new ToolBuildApprovedPlanPayload(
			toolPlan.getRawMarkdown(),
			readJson(toolPlan.getStructuredPlanJson()),
			readJson(toolPlan.getPlanSnapshot())
		);
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

	private String createToolPlanApprovalRequestMessageContent(ToolApproval toolApproval) {
		return """
			{"toolApprovalId":%d,"toolPlanId":%d,"planGroupId":%d,"planVersion":%d,"requestNumber":%d,"approvalStatus":"%s"}
			""".formatted(
			toolApproval.getId(),
			toolApproval.getToolPlan().getId(),
			toolApproval.getToolPlan().getPlanGroup().getId(),
			toolApproval.getToolPlan().getPlanVersion(),
			toolApproval.getRequestNumber(),
			toolApproval.getApprovalStatus()
		).trim();
	}

	private String createToolPlanRejectionNotice(ToolApproval toolApproval) {
		return """
			ToolPlan approval rejected. toolApprovalId=%d, toolPlanId=%d, requestNumber=%d
			""".formatted(
			toolApproval.getId(),
			toolApproval.getToolPlan().getId(),
			toolApproval.getRequestNumber()
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

	private ToolPlan getToolPlanForUpdate(Project project, Long toolPlanId) {
		return toolPlanRepository.findByIdAndProjectForUpdate(toolPlanId, project)
			.orElseThrow(() -> BusinessException.of(ErrorCode.TOOL_PLAN_NOT_FOUND));
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

	private void validateToolPlanCreator(ToolPlan toolPlan, ProjectMember projectMember) {
		if (!Objects.equals(toolPlan.getCreatedByProjectMember().getId(), projectMember.getId())) {
			throw BusinessException.of(ErrorCode.TOOL_APPROVAL_CREATOR_REQUIRED);
		}
	}

	private void validateRequestableTool(Tool tool) {
		if (!tool.canRequestApproval()) {
			throw BusinessException.of(ErrorCode.TOOL_APPROVAL_REVIEW_PHASE_REQUIRED);
		}
	}

	private void validateRequestableToolPlan(ToolPlan toolPlan) {
		ToolPlanGroup planGroup = toolPlan.getPlanGroup();
		if (!ToolPlanStatus.REVIEW.equals(toolPlan.getStatus())
			|| !ToolPlanGroupStatus.REVIEW.equals(planGroup.getStatus())) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_APPROVAL_REVIEW_STATUS_REQUIRED);
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

	private void validateToolGrade(ToolApprovalApproveRequest request) {
		if (request.getToolGrade() == null || request.getToolGrade() < 1) {
			throw BusinessException.of(ErrorCode.INVALID_INPUT_VALUE);
		}
	}

	private void validatePendingToolPlan(ToolPlan toolPlan) {
		if (!ToolPlanStatus.PENDING.equals(toolPlan.getStatus())
			|| !ToolPlanGroupStatus.PENDING.equals(toolPlan.getPlanGroup().getStatus())) {
			throw BusinessException.of(ErrorCode.TOOL_APPROVAL_PENDING_TOOL_REQUIRED);
		}
	}

	private JsonNode readJson(String value) {
		if (value == null || value.isBlank()) {
			return objectMapper.createObjectNode();
		}

		try {
			return objectMapper.readTree(value);
		} catch (JsonProcessingException exception) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_PAYLOAD_INVALID);
		}
	}

	private String writeAsJson(Object value) {
		try {
			return objectMapper.writeValueAsString(value);
		} catch (JsonProcessingException exception) {
			throw BusinessException.of(ErrorCode.INVALID_INPUT_VALUE);
		}
	}

	private String resolveErrorMessage(Throwable exception) {
		if (exception == null || exception.getMessage() == null || exception.getMessage().isBlank()) {
			return ErrorCode.TOOL_BUILD_KAFKA_PUBLISH_FAILED.getMessage();
		}

		return exception.getMessage();
	}

	private String createRunId() {
		return UUID.randomUUID().toString();
	}

	private Pageable createPageable(int page, int size) {
		return PageRequest.of(Math.max(page, 0), Math.max(size, 1));
	}
}
