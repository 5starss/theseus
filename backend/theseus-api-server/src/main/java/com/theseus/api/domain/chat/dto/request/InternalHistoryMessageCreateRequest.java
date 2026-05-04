package com.theseus.api.domain.chat.dto.request;

import com.theseus.api.domain.chat.entity.ChatMessageSenderType;
import com.theseus.api.domain.chat.entity.ChatMessageContentType;
import com.theseus.api.domain.chat.entity.ChatMessageType;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;

@Getter
public class InternalHistoryMessageCreateRequest {

	@NotNull
	private Long projectId;

	@NotNull
	private Long chatSessionId;

	private Long toolId;

	@NotNull
	private ChatMessageSenderType senderType;

	@NotBlank
	private String content;

	private ChatMessageType messageType;

	private ChatMessageContentType contentType;
}
