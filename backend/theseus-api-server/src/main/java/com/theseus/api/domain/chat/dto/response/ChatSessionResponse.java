package com.theseus.api.domain.chat.dto.response;

import com.theseus.api.domain.chat.entity.ChatSession;
import java.time.LocalDateTime;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ChatSessionResponse {

	private Long sessionId;
	private Long projectId;
	private Long projectMemberId;
	private String title;
	private Boolean isClosed;
	private LocalDateTime closedAt;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;

	public static ChatSessionResponse createFrom(ChatSession chatSession) {
		return ChatSessionResponse.builder()
			.sessionId(chatSession.getId())
			.projectId(chatSession.getProject().getId())
			.projectMemberId(chatSession.getProjectMember().getId())
			.title(chatSession.getTitle())
			.isClosed(chatSession.isClosed())
			.closedAt(chatSession.getClosedAt())
			.createdAt(chatSession.getCreatedAt())
			.updatedAt(chatSession.getUpdatedAt())
			.build();
	}
}
