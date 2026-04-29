package com.theseus.api.domain.chat.dto.response;

import com.theseus.api.domain.chat.entity.ChatMessage;
import com.theseus.api.domain.chat.entity.ChatSession;
import java.time.LocalDateTime;
import java.util.List;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ChatSessionDetailResponse {

	private Long sessionId;
	private Long projectId;
	private Long projectMemberId;
	private String title;
	private Boolean isClosed;
	private LocalDateTime closedAt;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;
	private List<ChatMessageResponse> messages;

	public static ChatSessionDetailResponse createOf(ChatSession chatSession, List<ChatMessage> messages) {
		return ChatSessionDetailResponse.builder()
			.sessionId(chatSession.getId())
			.projectId(chatSession.getProject().getId())
			.projectMemberId(chatSession.getProjectMember().getId())
			.title(chatSession.getTitle())
			.isClosed(chatSession.isClosed())
			.closedAt(chatSession.getClosedAt())
			.createdAt(chatSession.getCreatedAt())
			.updatedAt(chatSession.getUpdatedAt())
			.messages(messages.stream()
				.map(ChatMessageResponse::createFrom)
				.toList())
			.build();
	}
}
