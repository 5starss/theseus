package com.theseus.api.domain.billing.entity;

import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.user.entity.User;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
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
	name = "billing_usages",
	uniqueConstraints = {
		@UniqueConstraint(name = "uk_billing_usages_idempotency_key", columnNames = "idempotency_key")
	},
	indexes = {
		@Index(name = "idx_billing_usages_user_reported_at", columnList = "user_id, reported_at"),
		@Index(name = "idx_billing_usages_project_reported_at", columnList = "project_id, reported_at")
	}
)
@Entity
public class BillingUsage {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "user_id", nullable = false)
	private User user;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "project_id", nullable = false)
	private Project project;

	@Column(name = "prompt_tokens", nullable = false)
	private Long promptTokens;

	@Column(name = "completion_tokens", nullable = false)
	private Long completionTokens;

	@Column(name = "total_tokens", nullable = false)
	private Long totalTokens;

	@Column(name = "model_name", nullable = false, length = 120)
	private String modelName;

	@Column(name = "reported_at", nullable = false)
	private LocalDateTime reportedAt;

	@Column(name = "idempotency_key", length = 255)
	private String idempotencyKey;

	@Column(name = "usage_payload_json", nullable = false, columnDefinition = "LONGTEXT")
	private String usagePayloadJson;

	@Column(name = "created_at", nullable = false, updatable = false)
	private LocalDateTime createdAt;

	@Builder
	private BillingUsage(
		User user,
		Project project,
		Long promptTokens,
		Long completionTokens,
		Long totalTokens,
		String modelName,
		LocalDateTime reportedAt,
		String idempotencyKey,
		String usagePayloadJson
	) {
		this.user = user;
		this.project = project;
		this.promptTokens = promptTokens;
		this.completionTokens = completionTokens;
		this.totalTokens = totalTokens;
		this.modelName = modelName;
		this.reportedAt = reportedAt;
		this.idempotencyKey = idempotencyKey;
		this.usagePayloadJson = usagePayloadJson;
	}

	@PrePersist
	private void prePersist() {
		createdAt = LocalDateTime.now();
	}
}
