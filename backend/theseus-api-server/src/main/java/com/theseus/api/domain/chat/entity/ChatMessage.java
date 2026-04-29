package com.theseus.api.domain.chat.entity;

import com.theseus.api.domain.tool.entity.Tool;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.ForeignKey;
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
		@Index(name = "idx_chat_messages_session_order", columnList = "chat_session_id, message_order"),
		@Index(name = "idx_chat_messages_tool_order", columnList = "tool_id, message_order")
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

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "tool_id", foreignKey = @ForeignKey(name = "fk_chat_messages_tool"))
	private Tool tool;

	@Column(name = "message_order", nullable = false)
	private Integer messageOrder;

	@Enumerated(EnumType.STRING)
	@Column(name = "sender_type", nullable = false, length = 30)
	private ChatMessageSenderType senderType;

	@Enumerated(EnumType.STRING)
	@Column(name = "message_type", nullable = false, length = 50, columnDefinition = "VARCHAR(50) DEFAULT 'CHAT'")
	private ChatMessageType messageType;

	@Enumerated(EnumType.STRING)
	@Column(name = "content_type", nullable = false, length = 30, columnDefinition = "VARCHAR(30) DEFAULT 'TEXT'")
	private ChatMessageContentType contentType;

	@Column(nullable = false, columnDefinition = "MEDIUMTEXT")
	private String content;

	@Column(name = "created_at", nullable = false, updatable = false)
	private LocalDateTime createdAt;

	@Builder
	private ChatMessage(
		ChatSession chatSession,
		Tool tool,
		Integer messageOrder,
		ChatMessageSenderType senderType,
		ChatMessageType messageType,
		ChatMessageContentType contentType,
		String content
	) {
		this.chatSession = chatSession;
		this.tool = tool;
		this.messageOrder = messageOrder;
		this.senderType = senderType;
		this.messageType = messageType == null ? ChatMessageType.CHAT : messageType;
		this.contentType = contentType == null ? ChatMessageContentType.TEXT : contentType;
		this.content = content;
	}

	@PrePersist
	private void prePersist() {
		createdAt = LocalDateTime.now();
	}
}
