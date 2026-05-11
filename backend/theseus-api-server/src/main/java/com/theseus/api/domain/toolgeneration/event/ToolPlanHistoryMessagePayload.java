package com.theseus.api.domain.toolgeneration.event;

import com.theseus.api.domain.chat.entity.ChatMessageContentType;
import com.theseus.api.domain.chat.entity.ChatMessageType;

public record ToolPlanHistoryMessagePayload(
	String role,
	ChatMessageType messageType,
	ChatMessageContentType contentType,
	String content
) {
}
