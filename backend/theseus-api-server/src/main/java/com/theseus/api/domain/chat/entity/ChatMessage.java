package com.theseus.api.domain.chat.entity;

import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolPlan;
import com.theseus.api.domain.tool.entity.ToolPlanRun;
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
		@UniqueConstraint(name = "uk_chat_messages_session_order", columnNames = {"chat_session_id", "message_order"}),
		@UniqueConstraint(name = "uk_chat_messages_idempotency_key", columnNames = "idempotency_key")
	},
	indexes = {
		@Index(name = "idx_chat_messages_session_order", columnList = "chat_session_id, message_order"),
		@Index(name = "idx_chat_messages_tool_order", columnList = "tool_id, message_order"),
		@Index(name = "idx_chat_messages_tool_plan_order", columnList = "tool_plan_id, message_order"),
		@Index(name = "idx_chat_messages_tool_plan_run", columnList = "tool_plan_run_id")
	}
)
@Entity
public class ChatMessage {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(
		name = "chat_session_id",
		nullable = false,
		foreignKey = @ForeignKey(name = "fk_chat_messages_chat_session")
	)
	private ChatSession chatSession;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "tool_id", foreignKey = @ForeignKey(name = "fk_chat_messages_tool"))
	private Tool tool;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "tool_plan_id", foreignKey = @ForeignKey(name = "fk_chat_messages_tool_plan"))
	private ToolPlan toolPlan;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "tool_plan_run_id", foreignKey = @ForeignKey(name = "fk_chat_messages_tool_plan_run"))
	private ToolPlanRun toolPlanRun;

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

	@Column(name = "idempotency_key")
	private String idempotencyKey;

	@Column(name = "created_at", nullable = false, updatable = false)
	private LocalDateTime createdAt;

	@Builder
	private ChatMessage(
		ChatSession chatSession,
		Tool tool,
		ToolPlan toolPlan,
		ToolPlanRun toolPlanRun,
		Integer messageOrder,
		ChatMessageSenderType senderType,
		ChatMessageType messageType,
		ChatMessageContentType contentType,
		String content,
		String idempotencyKey
	) {
		this.chatSession = chatSession;
		this.tool = tool;
		this.toolPlan = toolPlan;
		this.toolPlanRun = toolPlanRun;
		this.messageOrder = messageOrder;
		this.senderType = senderType;
		this.messageType = messageType == null ? ChatMessageType.CHAT : messageType;
		this.contentType = contentType == null ? ChatMessageContentType.TEXT : contentType;
		this.content = content;
		this.idempotencyKey = idempotencyKey;
	}

	@PrePersist
	private void prePersist() {
		createdAt = LocalDateTime.now();
	}
}
