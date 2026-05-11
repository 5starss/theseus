package com.theseus.api.domain.toolgeneration.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.chat.entity.ChatMessageContentType;
import com.theseus.api.domain.chat.entity.ChatMessageSenderType;
import com.theseus.api.domain.chat.entity.ChatMessageType;
import com.theseus.api.domain.chat.service.ChatMessageService;
import com.theseus.api.domain.tool.entity.ToolPlan;
import com.theseus.api.domain.tool.entity.ToolPlanGroup;
import com.theseus.api.domain.tool.entity.ToolPlanRun;
import com.theseus.api.domain.tool.entity.ToolPlanStatus;
import com.theseus.api.domain.tool.repository.ToolPlanGroupRepository;
import com.theseus.api.domain.tool.repository.ToolPlanRepository;
import com.theseus.api.domain.tool.repository.ToolPlanRunRepository;
import com.theseus.api.domain.toolgeneration.event.ToolPlanAssistantMessagePayload;
import com.theseus.api.domain.toolgeneration.event.ToolPlanEvent;
import com.theseus.api.domain.toolgeneration.event.ToolPlanPayload;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.List;
import java.util.Objects;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ToolPlanEventService {

	private static final String SKIPPED_CODE = "TOOL_PLAN_SKIPPED";
	private static final String FAILED_CODE = "TOOL_PLAN_FAILED";
	private static final String DEFAULT_FAILED_MESSAGE = "Tool PLAN 생성에 실패했습니다.";

	private final ToolPlanRunRepository toolPlanRunRepository;
	private final ToolPlanGroupRepository toolPlanGroupRepository;
	private final ToolPlanRepository toolPlanRepository;
	private final ChatMessageService chatMessageService;
	private final ObjectMapper objectMapper;

	/**
	 * Core가 완성한 PLAN을 ToolPlan 버전으로 저장하고 실행 Run을 완료 처리합니다.
	 */
	@Transactional
	public void handleCompleted(ToolPlanEvent event) {
		toolPlanRunRepository.findByRunId(event.getRunId()).ifPresentOrElse(
			toolPlanRun -> {
				if (!hasSameProjectAndSession(event, toolPlanRun.getProject().getId(), toolPlanRun.getChatSession().getId())) {
					log.warn(">>>> ToolPlan completed event target mismatch. runId={}", event.getRunId());
					return;
				}
				if (toolPlanRun.isFinished()) {
					log.info(">>>> ToolPlan completed event skipped by terminal run. runId={}", event.getRunId());
					return;
				}

				ToolPlanPayload toolPlanPayload = requireToolPlan(event);
				ToolPlanAssistantMessagePayload assistantMessage = requireAssistantMessage(event);
				ChatMessageType messageType = resolveMessageType(
					assistantMessage.getMessageType(),
					ChatMessageType.TOOL_PLAN_RESPONSE
				);
				ChatMessageContentType contentType = resolveContentType(assistantMessage.getContentType());
				String assistantContent = resolveAssistantContent(assistantMessage, toolPlanPayload);

				ToolPlanGroup planGroup = resolvePlanGroup(toolPlanRun);
				supersedeLatestReviewPlan(planGroup);

				ToolPlan toolPlan = toolPlanRepository.save(ToolPlan.builder()
					.planGroup(planGroup)
					.project(toolPlanRun.getProject())
					.chatSession(toolPlanRun.getChatSession())
					.createdByProjectMember(toolPlanRun.getRequestedByProjectMember())
					.baseToolPlan(toolPlanRun.getBaseToolPlan())
					.planVersion(resolveNextPlanVersion(planGroup))
					.status(ToolPlanStatus.REVIEW)
					.mode(toolPlanRun.getMode())
					.requestedPrompt(resolveRequestedPrompt(toolPlanRun.getRequestPayloadJson()))
					.rawMarkdown(requireText(toolPlanPayload.getRawMarkdown()))
					.structuredPlanJson(writeJsonNodeAsString(toolPlanPayload.getStructuredPlanJson()))
					.planSnapshot(writeJsonNodeAsString(toolPlanPayload.getPlanSnapshot()))
					.build());

				planGroup.markReview(toolPlan);
				toolPlanRun.complete(toolPlan, parseCompletedAt(event));
				toolPlanRun.updateLastEvent(event.getEventType(), event.getEventSequence());
				chatMessageService.saveToolPlanEventMessage(
					toolPlanRun.getChatSession(),
					toolPlan,
					toolPlanRun,
					ChatMessageSenderType.ASSISTANT,
					messageType,
					contentType,
					assistantContent,
					createIdempotencyKey(event, "assistant")
				);

				log.info(
					">>>> ToolPlan completed event handled. runId={}, toolPlanId={}, version={}",
					event.getRunId(),
					toolPlan.getId(),
					toolPlan.getPlanVersion()
				);
			},
			() -> log.warn(">>>> ToolPlan completed event skipped. runId={} not found.", event.getRunId())
		);
	}

	/**
	 * Tool 명세 대상이 아닌 PLAN 요청을 SKIPPED로 처리하고 안내 메시지를 저장합니다.
	 */
	@Transactional
	public void handleSkipped(ToolPlanEvent event) {
		toolPlanRunRepository.findByRunId(event.getRunId()).ifPresentOrElse(
			toolPlanRun -> {
				if (!hasSameProjectAndSession(event, toolPlanRun.getProject().getId(), toolPlanRun.getChatSession().getId())) {
					log.warn(">>>> ToolPlan skipped event target mismatch. runId={}", event.getRunId());
					return;
				}
				if (toolPlanRun.isFinished()) {
					log.info(">>>> ToolPlan skipped event skipped by terminal run. runId={}", event.getRunId());
					return;
				}

				ToolPlanAssistantMessagePayload assistantMessage = requireAssistantMessage(event);
				ChatMessageType messageType = resolveMessageType(assistantMessage.getMessageType(), ChatMessageType.CHAT);
				ChatMessageContentType contentType = resolveContentType(assistantMessage.getContentType());
				String content = requireText(assistantMessage.getContent());

				toolPlanRun.skip(SKIPPED_CODE, content, parseCompletedAt(event));
				toolPlanRun.updateLastEvent(event.getEventType(), event.getEventSequence());
				chatMessageService.saveToolPlanEventMessage(
					toolPlanRun.getChatSession(),
					null,
					toolPlanRun,
					ChatMessageSenderType.ASSISTANT,
					messageType,
					contentType,
					content,
					createIdempotencyKey(event, "assistant")
				);

				log.info(">>>> ToolPlan skipped event handled. runId={}", event.getRunId());
			},
			() -> log.warn(">>>> ToolPlan skipped event skipped. runId={} not found.", event.getRunId())
		);
	}

	/**
	 * Core PLAN 생성 실패를 Run 상태와 System Notice 메시지로 기록합니다.
	 */
	@Transactional
	public void handleFailed(ToolPlanEvent event) {
		toolPlanRunRepository.findByRunId(event.getRunId()).ifPresentOrElse(
			toolPlanRun -> {
				if (!hasSameProjectAndSession(event, toolPlanRun.getProject().getId(), toolPlanRun.getChatSession().getId())) {
					log.warn(">>>> ToolPlan failed event target mismatch. runId={}", event.getRunId());
					return;
				}
				if (toolPlanRun.isFinished()) {
					log.info(">>>> ToolPlan failed event skipped by terminal run. runId={}", event.getRunId());
					return;
				}

				String code = resolveCode(event.getCode());
				String message = resolveFailedMessage(event.getMessage());
				toolPlanRun.fail(code, message, parseFailedAt(event));
				toolPlanRun.updateLastEvent(event.getEventType(), event.getEventSequence());
				chatMessageService.saveToolPlanEventMessage(
					toolPlanRun.getChatSession(),
					null,
					toolPlanRun,
					ChatMessageSenderType.SYSTEM,
					ChatMessageType.SYSTEM_NOTICE,
					ChatMessageContentType.TEXT,
					createFailedNoticeMessage(code, message),
					createIdempotencyKey(event, "system")
				);

				log.warn(">>>> ToolPlan failed event handled. runId={}, code={}", event.getRunId(), code);
			},
			() -> log.warn(">>>> ToolPlan failed event skipped. runId={} not found.", event.getRunId())
		);
	}

	private ToolPlanGroup resolvePlanGroup(ToolPlanRun toolPlanRun) {
		if (toolPlanRun.getPlanGroup() != null) {
			return toolPlanRun.getPlanGroup();
		}
		if (toolPlanRun.getBaseToolPlan() != null) {
			return toolPlanRun.getBaseToolPlan().getPlanGroup();
		}

		return toolPlanGroupRepository.save(ToolPlanGroup.builder()
			.project(toolPlanRun.getProject())
			.chatSession(toolPlanRun.getChatSession())
			.createdByProjectMember(toolPlanRun.getRequestedByProjectMember())
			.build());
	}

	private void supersedeLatestReviewPlan(ToolPlanGroup planGroup) {
		ToolPlan latestToolPlan = planGroup.getLatestToolPlan();
		if (latestToolPlan == null) {
			return;
		}
		if (ToolPlanStatus.REVIEW.equals(latestToolPlan.getStatus())
			|| ToolPlanStatus.REJECTED.equals(latestToolPlan.getStatus())) {
			latestToolPlan.supersede();
		}
	}

	private Long resolveNextPlanVersion(ToolPlanGroup planGroup) {
		List<ToolPlan> toolPlans = toolPlanRepository.findByPlanGroupOrderByPlanVersionDesc(planGroup);
		if (toolPlans.isEmpty()) {
			return 1L;
		}

		return toolPlans.get(0).getPlanVersion() + 1;
	}

	private ToolPlanPayload requireToolPlan(ToolPlanEvent event) {
		if (event.getToolPlan() == null) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_EVENT_INVALID);
		}
		return event.getToolPlan();
	}

	private ToolPlanAssistantMessagePayload requireAssistantMessage(ToolPlanEvent event) {
		if (event.getAssistantMessage() == null) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_EVENT_INVALID);
		}
		return event.getAssistantMessage();
	}

	private ChatMessageType resolveMessageType(String messageType, ChatMessageType expectedMessageType) {
		if (messageType == null || messageType.isBlank()) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_EVENT_INVALID);
		}

		try {
			ChatMessageType resolvedMessageType = ChatMessageType.valueOf(messageType);
			if (!expectedMessageType.equals(resolvedMessageType)) {
				throw BusinessException.of(ErrorCode.TOOL_PLAN_EVENT_INVALID);
			}
			return resolvedMessageType;
		} catch (IllegalArgumentException exception) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_EVENT_INVALID, exception);
		}
	}

	private ChatMessageContentType resolveContentType(String contentType) {
		if (contentType == null || contentType.isBlank()) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_EVENT_INVALID);
		}

		try {
			return ChatMessageContentType.valueOf(contentType);
		} catch (IllegalArgumentException exception) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_EVENT_INVALID, exception);
		}
	}

	private String resolveAssistantContent(
		ToolPlanAssistantMessagePayload assistantMessage,
		ToolPlanPayload toolPlanPayload
	) {
		if (assistantMessage.getContent() != null && !assistantMessage.getContent().isBlank()) {
			return assistantMessage.getContent();
		}
		return requireText(toolPlanPayload.getRawMarkdown());
	}

	private String requireText(String value) {
		if (value == null || value.isBlank()) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_EVENT_INVALID);
		}
		return value;
	}

	private String writeJsonNodeAsString(JsonNode jsonNode) {
		if (jsonNode == null || jsonNode.isNull()) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_EVENT_INVALID);
		}

		try {
			return objectMapper.writeValueAsString(jsonNode);
		} catch (JsonProcessingException exception) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_EVENT_INVALID, exception);
		}
	}

	private boolean hasSameProjectAndSession(ToolPlanEvent event, Long projectId, Long chatSessionId) {
		return Objects.equals(event.getProjectId(), projectId)
			&& Objects.equals(event.getChatSessionId(), chatSessionId);
	}

	private LocalDateTime parseCompletedAt(ToolPlanEvent event) {
		return parseDateTime(event.getCompletedAt());
	}

	private LocalDateTime parseFailedAt(ToolPlanEvent event) {
		return parseDateTime(event.getFailedAt());
	}

	private LocalDateTime parseDateTime(String value) {
		if (value == null || value.isBlank()) {
			return LocalDateTime.now();
		}

		try {
			return OffsetDateTime.parse(value).toLocalDateTime();
		} catch (DateTimeParseException ignored) {
			try {
				return LocalDateTime.parse(value);
			} catch (DateTimeParseException exception) {
				log.warn(">>>> ToolPlan event datetime parse failed. value={}", value);
				return LocalDateTime.now();
			}
		}
	}

	private String resolveRequestedPrompt(String requestPayloadJson) {
		if (requestPayloadJson == null || requestPayloadJson.isBlank()) {
			return null;
		}

		try {
			JsonNode root = objectMapper.readTree(requestPayloadJson);
			JsonNode promptNode = root.get("prompt");
			if (promptNode == null || promptNode.isNull()) {
				return null;
			}
			return promptNode.asText();
		} catch (JsonProcessingException exception) {
			log.warn(">>>> ToolPlanRun request payload parse failed.");
			return null;
		}
	}

	private String createIdempotencyKey(ToolPlanEvent event, String suffix) {
		return "tool-plan-event:" + event.getRunId() + ":" + event.getEventType() + ":" + suffix;
	}

	private String resolveCode(String code) {
		if (code == null || code.isBlank()) {
			return FAILED_CODE;
		}
		return code;
	}

	private String resolveFailedMessage(String message) {
		if (message == null || message.isBlank()) {
			return DEFAULT_FAILED_MESSAGE;
		}
		return message;
	}

	private String createFailedNoticeMessage(String code, String message) {
		return DEFAULT_FAILED_MESSAGE + " code=" + code + ", message=" + message;
	}
}
