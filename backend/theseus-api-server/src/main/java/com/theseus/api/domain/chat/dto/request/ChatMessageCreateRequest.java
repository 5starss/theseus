package com.theseus.api.domain.chat.dto.request;

import com.theseus.api.domain.chat.entity.ChatMessageContentType;
import com.theseus.api.domain.chat.entity.ChatMessageType;
import jakarta.validation.constraints.NotBlank;
import lombok.Getter;

@Getter
public class ChatMessageCreateRequest {

	@NotBlank
	private String content;

	private ChatMessageType messageType;

	private ChatMessageContentType contentType;
}
