package com.theseus.api.domain.chat.dto.response;

import com.theseus.api.domain.chat.entity.ChatMessage;
import com.theseus.api.domain.chat.entity.ChatMessageContentType;
import com.theseus.api.domain.chat.entity.ChatMessageSenderType;
import com.theseus.api.domain.chat.entity.ChatMessageType;
import java.time.LocalDateTime;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ChatMessageResponse {

	private Long messageId;
	private Long chatSessionId;
	private Long toolId;
	private Integer messageOrder;
	private ChatMessageSenderType senderType;
	private ChatMessageType messageType;
	private ChatMessageContentType contentType;
	private String content;
	private LocalDateTime createdAt;

	public static ChatMessageResponse createFrom(ChatMessage chatMessage) {
		return ChatMessageResponse.builder()
			.messageId(chatMessage.getId())
			.chatSessionId(chatMessage.getChatSession().getId())
			.toolId(chatMessage.getTool() == null ? null : chatMessage.getTool().getId())
			.messageOrder(chatMessage.getMessageOrder())
			.senderType(chatMessage.getSenderType())
			.messageType(chatMessage.getMessageType())
			.contentType(chatMessage.getContentType())
			.content(chatMessage.getContent())
			.createdAt(chatMessage.getCreatedAt())
			.build();
	}
}
