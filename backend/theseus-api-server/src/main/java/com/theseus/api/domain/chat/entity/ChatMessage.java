package com.theseus.api.domain.chat.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import java.time.LocalDateTime;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
	name = "chat_messages",
	uniqueConstraints = {
		@UniqueConstraint(name = "uk_chat_messages_session_order", columnNames = {"chat_session_id", "message_order"})
	},
	indexes = {
		@Index(name = "idx_chat_messages_session_order", columnList = "chat_session_id, message_order")
	}
)
@Entity
public class ChatMessage {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "chat_session_id", nullable = false)
	private ChatSession chatSession;

	@Column(name = "message_order", nullable = false)
	private Integer messageOrder;

	@Enumerated(EnumType.STRING)
	@Column(name = "sender_type", nullable = false, length = 30)
	private ChatMessageSenderType senderType;

	@Column(nullable = false, columnDefinition = "MEDIUMTEXT")
	private String content;

	@Column(name = "created_at", nullable = false, updatable = false)
	private LocalDateTime createdAt;

	@Builder
	private ChatMessage(
		ChatSession chatSession,
		Integer messageOrder,
		ChatMessageSenderType senderType,
		String content
	) {
		this.chatSession = chatSession;
		this.messageOrder = messageOrder;
		this.senderType = senderType;
		this.content = content;
	}

	@PrePersist
	private void prePersist() {
		createdAt = LocalDateTime.now();
	}
}
