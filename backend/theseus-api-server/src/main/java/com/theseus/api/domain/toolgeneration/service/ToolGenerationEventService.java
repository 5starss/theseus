package com.theseus.api.domain.toolgeneration.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.chat.entity.ChatMessageContentType;
import com.theseus.api.domain.chat.entity.ChatMessageType;
import com.theseus.api.domain.chat.service.ChatMessageService;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolDraftPhase;
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.toolgeneration.dto.ToolGenerationSseEvent;
import com.theseus.api.domain.toolgeneration.dto.ToolGenerationState;
import com.theseus.api.domain.toolgeneration.event.ToolGenerationAssistantMessagePayload;
import com.theseus.api.domain.toolgeneration.event.ToolGenerationDraftPayload;
import com.theseus.api.domain.toolgeneration.event.ToolGenerationEvent;
import com.theseus.api.domain.toolgeneration.redis.ToolGenerationStateStore;
import com.theseus.api.domain.toolgeneration.sse.ToolGenerationSseEmitterRegistry;
import java.time.LocalDateTime;
import java.util.Optional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

@Slf4j
@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ToolGenerationEventService {

	private static final String DEFAULT_FAILED_MESSAGE = "Tool PLAN 생성에 실패했습니다.";

	private static final String EVENT_TYPE_PROGRESS = "progress";
	private static final String EVENT_TYPE_CHUNK = "chunk";
	private static final String EVENT_TYPE_COMPLETED = "completed";
	private static final String EVENT_TYPE_FAILED = "failed";
	private static final String STATUS_GENERATING = "GENERATING";
	private static final String STATUS_COMPLETED = "COMPLETED";
	private static final String STATUS_FAILED = "FAILED";
	private static final String COMPLETED_MESSAGE = "Tool PLAN 생성이 완료되었습니다.";

	private final ToolRepository toolRepository;
	private final ChatMessageService chatMessageService;
	private final ObjectMapper objectMapper;
	private final ToolGenerationStateStore toolGenerationStateStore;
	private final ToolGenerationSseEmitterRegistry toolGenerationSseEmitterRegistry;

	/**
	 * Core Server의 progress 이벤트를 Redis 최신 상태로 저장하고 SSE로 전달합니다.
	 */
	public void handleProgress(ToolGenerationEvent event) {
		if (!hasRequiredStateIds(event)) {
			log.warn(
				">>>> Tool generation progress state skipped. runId={}, projectId={}, chatSessionId={}, toolId={}",
				event.getRunId(),
				event.getProjectId(),
				event.getChatSessionId(),
				event.getToolId()
			);
			return;
		}

		ToolGenerationState state = createProgressState(event);
		saveStateAndSend(EVENT_TYPE_PROGRESS, state, () -> toolGenerationStateStore.saveProgress(state));
	}

	/**
	 * Core Server의 chunk 이벤트를 Redis 최신 상태로 저장하고 SSE로 전달합니다.
	 */
	public void handleChunk(ToolGenerationEvent event) {
		if (!hasRequiredStateIds(event)) {
			log.warn(
				">>>> Tool generation chunk state skipped. runId={}, projectId={}, chatSessionId={}, toolId={}",
				event.getRunId(),
				event.getProjectId(),
				event.getChatSessionId(),
				event.getToolId()
			);
			return;
		}

		ToolGenerationState state = createChunkState(event);
		saveStateAndSend(EVENT_TYPE_CHUNK, state, () -> toolGenerationStateStore.saveChunk(state));
	}

	/**
	 * Tool 생성 완료 이벤트를 DB에 반영한 뒤 Redis와 SSE에 완료 상태를 전달합니다.
	 */
	@Transactional
	public void handleCompleted(ToolGenerationEvent event) {
		Optional<Tool> optionalTool = findEventTool(event);
		if (optionalTool.isEmpty()) {
			log.warn(
				">>>> Tool generation completed event skipped. runId={}, projectId={}, chatSessionId={}, toolId={}",
				event.getRunId(),
				event.getProjectId(),
				event.getChatSessionId(),
				event.getToolId()
			);
			return;
		}

		Tool tool = optionalTool.get();
		ToolGenerationDraftPayload toolDraft = requireToolDraft(event);
		ToolGenerationAssistantMessagePayload assistantMessage = requireAssistantMessage(event);
		ChatMessageType messageType = resolveAssistantMessageType(assistantMessage.getMessageType());
		ChatMessageContentType contentType = resolveContentType(assistantMessage.getContentType());
		String assistantContent = resolveAssistantContent(assistantMessage, toolDraft);

		tool.completeDraftReview(
			toolDraft.getRawMarkdown(),
			writeJsonNodeAsString(toolDraft.getStructuredPlanJson()),
			writeJsonNodeAsString(toolDraft.getDraftSnapshot())
		);
		chatMessageService.saveAssistantMessage(
			tool.getChatSession(),
			tool,
			messageType,
			contentType,
			assistantContent
		);

		ToolGenerationState state = createCompletedState(event, tool);
		saveStateAfterCommit(() -> {
			if (saveStateSafely(EVENT_TYPE_COMPLETED, state, () -> toolGenerationStateStore.saveCompleted(state))) {
				sendStateToSse(state);
				completeSse(state);
			}
		});

		log.info(
			">>>> Tool generation completed event handled. runId={}, chatSessionId={}, toolId={}",
			event.getRunId(),
			event.getChatSessionId(),
			event.getToolId()
		);
	}

	/**
	 * Tool 생성 실패 이벤트를 DB에 기록한 뒤 Redis와 SSE에 실패 상태를 전달합니다.
	 */
	@Transactional
	public void handleFailed(ToolGenerationEvent event) {
		Optional<Tool> optionalTool = findEventTool(event);
		if (optionalTool.isEmpty()) {
			log.warn(
				">>>> Tool generation failed event skipped. runId={}, projectId={}, chatSessionId={}, toolId={}, code={}",
				event.getRunId(),
				event.getProjectId(),
				event.getChatSessionId(),
				event.getToolId(),
				event.getCode()
			);
			return;
		}

		Tool tool = optionalTool.get();
		tool.markAsPlan();
		chatMessageService.saveSystemNoticeMessage(
			tool.getChatSession(),
			tool,
			createFailedNoticeMessage(event)
		);

		ToolGenerationState state = createFailedState(event);
		saveStateAfterCommit(() -> {
			if (saveStateSafely(EVENT_TYPE_FAILED, state, () -> toolGenerationStateStore.saveFailed(state))) {
				sendStateToSse(state);
				completeSse(state);
			}
		});

		log.warn(
			">>>> Tool generation failed event handled. runId={}, chatSessionId={}, toolId={}, code={}, message={}",
			event.getRunId(),
			event.getChatSessionId(),
			event.getToolId(),
			event.getCode(),
			event.getMessage()
		);
	}

	/**
	 * Redis 상태 저장에 필요한 식별자가 모두 포함되어 있는지 확인합니다.
	 */
	private boolean hasRequiredStateIds(ToolGenerationEvent event) {
		return event.getToolId() != null
			&& event.getProjectId() != null
			&& event.getChatSessionId() != null;
	}

	/**
	 * progress 이벤트를 Redis와 SSE에서 사용할 상태 객체로 변환합니다.
	 */
	private ToolGenerationState createProgressState(ToolGenerationEvent event) {
		return ToolGenerationState.builder()
			.projectId(event.getProjectId())
			.chatSessionId(event.getChatSessionId())
			.toolId(event.getToolId())
			.eventType(EVENT_TYPE_PROGRESS)
			.status(STATUS_GENERATING)
			.draftPhase(ToolDraftPhase.PLAN.name())
			.message(event.getMessage())
			.progressRate(event.getProgressRate())
			.updatedAt(LocalDateTime.now())
			.build();
	}

	/**
	 * chunk 이벤트를 Redis와 SSE에서 사용할 상태 객체로 변환합니다.
	 */
	private ToolGenerationState createChunkState(ToolGenerationEvent event) {
		return ToolGenerationState.builder()
			.projectId(event.getProjectId())
			.chatSessionId(event.getChatSessionId())
			.toolId(event.getToolId())
			.eventType(EVENT_TYPE_CHUNK)
			.status(STATUS_GENERATING)
			.draftPhase(ToolDraftPhase.PLAN.name())
			.content(event.getContent())
			.updatedAt(LocalDateTime.now())
			.build();
	}

	/**
	 * DB 반영이 끝난 completed 이벤트를 최종 상태 객체로 변환합니다.
	 */
	private ToolGenerationState createCompletedState(ToolGenerationEvent event, Tool tool) {
		return ToolGenerationState.builder()
			.projectId(event.getProjectId())
			.chatSessionId(event.getChatSessionId())
			.toolId(event.getToolId())
			.eventType(EVENT_TYPE_COMPLETED)
			.status(STATUS_COMPLETED)
			.draftPhase(ToolDraftPhase.REVIEW.name())
			.draftVersion(toInteger(tool.getDraftVersion()))
			.message(COMPLETED_MESSAGE)
			.updatedAt(LocalDateTime.now())
			.build();
	}

	/**
	 * failed 이벤트를 Redis와 SSE에서 사용할 실패 상태 객체로 변환합니다.
	 */
	private ToolGenerationState createFailedState(ToolGenerationEvent event) {
		return ToolGenerationState.builder()
			.projectId(event.getProjectId())
			.chatSessionId(event.getChatSessionId())
			.toolId(event.getToolId())
			.eventType(EVENT_TYPE_FAILED)
			.status(STATUS_FAILED)
			.errorCode(event.getCode())
			.errorMessage(event.getMessage())
			.updatedAt(LocalDateTime.now())
			.build();
	}

	private Integer toInteger(Long value) {
		return value == null ? null : value.intValue();
	}

	/**
	 * Redis 저장 성공 시에만 SSE 이벤트를 전송합니다.
	 */
	private void saveStateAndSend(String eventType, ToolGenerationState state, Runnable saveAction) {
		if (saveStateSafely(eventType, state, saveAction)) {
			sendStateToSse(state);
		}
	}

	/**
	 * completed/failed 최종 상태 저장은 DB 트랜잭션 커밋 이후 실행합니다.
	 */
	private void saveStateAfterCommit(Runnable saveAction) {
		if (!TransactionSynchronizationManager.isSynchronizationActive()) {
			saveAction.run();
			return;
		}

		TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
			@Override
			public void afterCommit() {
				saveAction.run();
			}
		});
	}

	/**
	 * Redis 저장 실패가 Kafka Consumer 처리를 중단하지 않도록 격리합니다.
	 */
	private boolean saveStateSafely(String eventType, ToolGenerationState state, Runnable saveAction) {
		try {
			saveAction.run();
			return true;
		} catch (RuntimeException exception) {
			log.warn(
				">>>> Failed to save Tool generation Redis state. eventType={}, toolId={}",
				eventType,
				state.getToolId(),
				exception
			);
			return false;
		}
	}

	/**
	 * Redis에 저장한 Tool 생성 상태를 연결된 SSE 구독자에게 전달합니다.
	 */
	private void sendStateToSse(ToolGenerationState state) {
		toolGenerationSseEmitterRegistry.sendToTool(
			state.getProjectId(),
			state.getChatSessionId(),
			state.getToolId(),
			ToolGenerationSseEvent.createFrom(state)
		);
	}

	/**
	 * completed/failed 최종 이벤트 이후 SSE 연결을 정리합니다.
	 */
	private void completeSse(ToolGenerationState state) {
		toolGenerationSseEmitterRegistry.complete(
			state.getProjectId(),
			state.getChatSessionId(),
			state.getToolId()
		);
	}

	private Optional<Tool> findEventTool(ToolGenerationEvent event) {
		if (event.getToolId() == null || event.getProjectId() == null || event.getChatSessionId() == null) {
			return Optional.empty();
		}

		return toolRepository.findByIdAndProjectIdAndChatSessionIdForUpdate(
			event.getToolId(),
			event.getProjectId(),
			event.getChatSessionId()
		);
	}

	private ToolGenerationDraftPayload requireToolDraft(ToolGenerationEvent event) {
		if (event.getToolDraft() == null) {
			throw BusinessException.of(ErrorCode.TOOL_GENERATION_EVENT_INVALID);
		}
		return event.getToolDraft();
	}

	private ToolGenerationAssistantMessagePayload requireAssistantMessage(ToolGenerationEvent event) {
		if (event.getAssistantMessage() == null) {
			throw BusinessException.of(ErrorCode.TOOL_GENERATION_EVENT_INVALID);
		}
		return event.getAssistantMessage();
	}

	private ChatMessageType resolveAssistantMessageType(String messageType) {
		ChatMessageType resolvedMessageType;
		try {
			resolvedMessageType = ChatMessageType.valueOf(messageType);
		} catch (IllegalArgumentException exception) {
			throw BusinessException.of(ErrorCode.TOOL_GENERATION_EVENT_INVALID, exception);
		}
		if (
			!ChatMessageType.TOOL_DRAFT_RESPONSE.equals(resolvedMessageType)
				&& !ChatMessageType.TOOL_REGENERATE_RESPONSE.equals(resolvedMessageType)
		) {
			throw BusinessException.of(ErrorCode.TOOL_GENERATION_EVENT_INVALID);
		}
		return resolvedMessageType;
	}

	private ChatMessageContentType resolveContentType(String contentType) {
		try {
			return ChatMessageContentType.valueOf(contentType);
		} catch (IllegalArgumentException exception) {
			throw BusinessException.of(ErrorCode.TOOL_GENERATION_EVENT_INVALID, exception);
		}
	}

	private String resolveAssistantContent(
		ToolGenerationAssistantMessagePayload assistantMessage,
		ToolGenerationDraftPayload toolDraft
	) {
		if (assistantMessage.getContent() != null && !assistantMessage.getContent().isBlank()) {
			return assistantMessage.getContent();
		}
		if (toolDraft.getRawMarkdown() != null && !toolDraft.getRawMarkdown().isBlank()) {
			return toolDraft.getRawMarkdown();
		}
		throw BusinessException.of(ErrorCode.TOOL_GENERATION_EVENT_INVALID);
	}

	private String writeJsonNodeAsString(JsonNode jsonNode) {
		if (jsonNode == null || jsonNode.isNull()) {
			return null;
		}

		try {
			return objectMapper.writeValueAsString(jsonNode);
		} catch (JsonProcessingException exception) {
			throw BusinessException.of(ErrorCode.TOOL_GENERATION_EVENT_INVALID, exception);
		}
	}

	private String createFailedNoticeMessage(ToolGenerationEvent event) {
		String code = event.getCode() == null || event.getCode().isBlank()
			? "UNKNOWN"
			: event.getCode();
		String message = event.getMessage() == null || event.getMessage().isBlank()
			? DEFAULT_FAILED_MESSAGE
			: event.getMessage();

		return DEFAULT_FAILED_MESSAGE + " code=" + code + ", message=" + message;
	}
}
