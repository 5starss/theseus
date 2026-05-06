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
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.toolgeneration.event.ToolGenerationAssistantMessagePayload;
import com.theseus.api.domain.toolgeneration.event.ToolGenerationDraftPayload;
import com.theseus.api.domain.toolgeneration.event.ToolGenerationEvent;
import java.util.Optional;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ToolGenerationEventService {

	private static final String DEFAULT_FAILED_MESSAGE = "Tool PLAN 생성에 실패했습니다.";

	private final ToolRepository toolRepository;
	private final ChatMessageService chatMessageService;
	private final ObjectMapper objectMapper;

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

		log.info(
			">>>> Tool generation completed event handled. runId={}, chatSessionId={}, toolId={}",
			event.getRunId(),
			event.getChatSessionId(),
			event.getToolId()
		);
	}

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

		log.warn(
			">>>> Tool generation failed event handled. runId={}, chatSessionId={}, toolId={}, code={}, message={}",
			event.getRunId(),
			event.getChatSessionId(),
			event.getToolId(),
			event.getCode(),
			event.getMessage()
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
