package com.theseus.api.domain.toolgeneration.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.entity.ChatMessage;
import com.theseus.api.domain.chat.entity.ChatMessageContentType;
import com.theseus.api.domain.chat.entity.ChatMessageType;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.chat.repository.ChatMessageRepository;
import com.theseus.api.domain.chat.repository.ChatSessionRepository;
import com.theseus.api.domain.chat.service.ChatMessageService;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.tool.entity.ToolPlanMode;
import com.theseus.api.domain.tool.entity.ToolPlanRun;
import com.theseus.api.domain.tool.entity.ToolPlanRunRequestType;
import com.theseus.api.domain.tool.entity.ToolPlanRunStatus;
import com.theseus.api.domain.tool.repository.ToolPlanRunRepository;
import com.theseus.api.domain.toolgeneration.dto.request.ToolPlanGenerationRequest;
import com.theseus.api.domain.toolgeneration.dto.response.ToolPlanGenerationRunResponse;
import com.theseus.api.domain.toolgeneration.event.ToolPlanGenerationRequestEvent;
import com.theseus.api.domain.toolgeneration.event.ToolPlanHistoryMessagePayload;
import com.theseus.api.domain.toolgeneration.event.ToolPlanKafkaPublishEvent;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Locale;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ToolPlanGenerationService {

	private static final String TOOL_PLAN_REQUESTED = "TOOL_PLAN_REQUESTED";
	private static final int HISTORY_LIMIT = 30;

	private final ToolPlanRunRepository toolPlanRunRepository;
	private final ChatSessionRepository chatSessionRepository;
	private final ChatMessageRepository chatMessageRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final UserRepository userRepository;
	private final ChatMessageService chatMessageService;
	private final ApplicationEventPublisher eventPublisher;
	private final ObjectMapper objectMapper;

	/**
	 * PLAN 생성 요청을 ToolPlanRun으로 기록하고 Kafka 요청 이벤트를 발행합니다.
	 */
	@Transactional
	public ToolPlanGenerationRunResponse generatePlan(
		AuthenticatedUser currentUser,
		Long projectId,
		Long sessionId,
		ToolPlanGenerationRequest request
	) {
		validatePlanMode(request.getMode());

		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);
		validateToolCreatePermission(projectMember);

		ChatSession chatSession = getAccessibleChatSessionForUpdate(sessionId, project, projectMember);
		validateOpenChatSession(chatSession);

		List<ToolPlanHistoryMessagePayload> history = createHistorySnapshot(chatSession);
		String runId = createRunId();
		LocalDateTime requestedAt = LocalDateTime.now();
		ToolPlanGenerationRequestEvent requestEvent = createRequestEvent(
			runId,
			project,
			chatSession,
			projectMember,
			request,
			history,
			requestedAt
		);

		ToolPlanRun toolPlanRun = toolPlanRunRepository.save(ToolPlanRun.builder()
			.runId(runId)
			.project(project)
			.chatSession(chatSession)
			.requestType(ToolPlanRunRequestType.GENERATE_PLAN)
			.mode(ToolPlanMode.PLAN)
			.status(ToolPlanRunStatus.REQUESTED)
			.requestedByProjectMember(projectMember)
			.requestPayloadJson(writeAsJson(requestEvent))
			.historySnapshotJson(writeAsJson(history))
			.requestedAt(requestedAt)
			.build());

		ChatMessage userMessage = chatMessageService.saveUserToolPlanRunMessage(
			chatSession,
			toolPlanRun,
			ChatMessageType.TOOL_PLAN_REQUEST,
			ChatMessageContentType.TEXT,
			request.getPrompt()
		);
		toolPlanRun.attachUserMessageId(userMessage.getId());

		eventPublisher.publishEvent(new ToolPlanKafkaPublishEvent(runId, requestEvent));
		return ToolPlanGenerationRunResponse.createFrom(toolPlanRun);
	}

	/**
	 * Kafka 발행 실패를 별도 트랜잭션으로 ToolPlanRun에 기록합니다.
	 */
	@Transactional(propagation = Propagation.REQUIRES_NEW)
	public void markRunPublishFailed(String runId, Throwable exception) {
		toolPlanRunRepository.findByRunId(runId).ifPresentOrElse(
			toolPlanRun -> {
				if (toolPlanRun.isFinished()) {
					return;
				}

				toolPlanRun.fail(
					ErrorCode.TOOL_PLAN_KAFKA_PUBLISH_FAILED.getCode(),
					resolveErrorMessage(exception),
					LocalDateTime.now()
				);
			},
			() -> log.warn(">>>> ToolPlanRun을 찾을 수 없어 Kafka 발행 실패를 기록하지 못했습니다. runId={}", runId)
		);
	}

	private ToolPlanGenerationRequestEvent createRequestEvent(
		String runId,
		Project project,
		ChatSession chatSession,
		ProjectMember projectMember,
		ToolPlanGenerationRequest request,
		List<ToolPlanHistoryMessagePayload> history,
		LocalDateTime requestedAt
	) {
		return new ToolPlanGenerationRequestEvent(
			TOOL_PLAN_REQUESTED,
			ToolPlanMode.PLAN,
			runId,
			project.getId(),
			chatSession.getId(),
			projectMember.getUser().getId(),
			projectMember.getId(),
			request.getPrompt(),
			history,
			requestedAt
		);
	}

	private List<ToolPlanHistoryMessagePayload> createHistorySnapshot(ChatSession chatSession) {
		List<ChatMessage> messages = chatMessageRepository.findByChatSessionOrderByMessageOrderAsc(chatSession);
		int fromIndex = Math.max(messages.size() - HISTORY_LIMIT, 0);

		return messages.subList(fromIndex, messages.size()).stream()
			.map(this::createHistoryMessageFrom)
			.toList();
	}

	private ToolPlanHistoryMessagePayload createHistoryMessageFrom(ChatMessage chatMessage) {
		return new ToolPlanHistoryMessagePayload(
			chatMessage.getSenderType().name().toLowerCase(Locale.ROOT),
			chatMessage.getMessageType(),
			chatMessage.getContentType(),
			chatMessage.getContent()
		);
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

	private ChatSession getAccessibleChatSessionForUpdate(
		Long sessionId,
		Project project,
		ProjectMember projectMember
	) {
		return chatSessionRepository.findByIdAndProjectAndProjectMemberForUpdate(sessionId, project, projectMember)
			.orElseThrow(() -> BusinessException.of(ErrorCode.CHAT_SESSION_NOT_FOUND));
	}

	private void validatePlanMode(ToolPlanMode mode) {
		if (!ToolPlanMode.PLAN.equals(mode)) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_REQUEST_MODE_INVALID);
		}
	}

	private void validateToolCreatePermission(ProjectMember projectMember) {
		if (!Boolean.TRUE.equals(projectMember.getCanCreateTool())) {
			throw BusinessException.of(ErrorCode.TOOL_CREATE_PERMISSION_REQUIRED);
		}
	}

	private void validateOpenChatSession(ChatSession chatSession) {
		if (chatSession.isClosed()) {
			throw BusinessException.of(ErrorCode.CLOSED_CHAT_SESSION);
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
			return ErrorCode.TOOL_PLAN_KAFKA_PUBLISH_FAILED.getMessage();
		}

		return exception.getMessage();
	}

	private String createRunId() {
		return UUID.randomUUID().toString();
	}
}
