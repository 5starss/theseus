package com.theseus.api.domain.tool.entity;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
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
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import jakarta.persistence.UniqueConstraint;
import java.time.LocalDateTime;
import java.util.Objects;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
	name = "tool_plans",
	uniqueConstraints = {
		@UniqueConstraint(name = "uk_tool_plans_group_version", columnNames = {"plan_group_id", "plan_version"})
	},
	indexes = {
		@Index(name = "idx_tool_plans_group_status", columnList = "plan_group_id, status")
	}
)
@Entity
public class ToolPlan {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "plan_group_id", nullable = false, foreignKey = @ForeignKey(name = "fk_tool_plans_group"))
	private ToolPlanGroup planGroup;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "project_id", nullable = false, foreignKey = @ForeignKey(name = "fk_tool_plans_project"))
	private Project project;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(
		name = "chat_session_id",
		nullable = false,
		foreignKey = @ForeignKey(name = "fk_tool_plans_chat_session")
	)
	private ChatSession chatSession;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(
		name = "created_by_project_member_id",
		nullable = false,
		foreignKey = @ForeignKey(name = "fk_tool_plans_created_by_project_member")
	)
	private ProjectMember createdByProjectMember;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "base_tool_plan_id", foreignKey = @ForeignKey(name = "fk_tool_plans_base_tool_plan"))
	private ToolPlan baseToolPlan;

	@Column(name = "plan_version", nullable = false)
	private Long planVersion;

	@Enumerated(EnumType.STRING)
	@Column(nullable = false, length = 30, columnDefinition = "VARCHAR(30) DEFAULT 'REVIEW'")
	private ToolPlanStatus status;

	@Enumerated(EnumType.STRING)
	@Column(nullable = false, length = 30, columnDefinition = "VARCHAR(30) DEFAULT 'PLAN'")
	private ToolPlanMode mode;

	@Column(name = "requested_prompt", columnDefinition = "LONGTEXT")
	private String requestedPrompt;

	@Column(name = "raw_markdown", nullable = false, columnDefinition = "LONGTEXT")
	private String rawMarkdown;

	@Column(name = "structured_plan_json", nullable = false, columnDefinition = "LONGTEXT")
	private String structuredPlanJson;

	@Column(name = "plan_snapshot", nullable = false, columnDefinition = "LONGTEXT")
	private String planSnapshot;

	@Column(name = "created_at", nullable = false, updatable = false)
	private LocalDateTime createdAt;

	@Column(name = "updated_at", nullable = false)
	private LocalDateTime updatedAt;

	@Builder
	private ToolPlan(
		ToolPlanGroup planGroup,
		Project project,
		ChatSession chatSession,
		ProjectMember createdByProjectMember,
		ToolPlan baseToolPlan,
		Long planVersion,
		ToolPlanStatus status,
		ToolPlanMode mode,
		String requestedPrompt,
		String rawMarkdown,
		String structuredPlanJson,
		String planSnapshot
	) {
		this.planGroup = Objects.requireNonNull(planGroup, "planGroup must not be null");
		this.project = Objects.requireNonNull(project, "project must not be null");
		this.chatSession = Objects.requireNonNull(chatSession, "chatSession must not be null");
		this.createdByProjectMember = Objects.requireNonNull(
			createdByProjectMember,
			"createdByProjectMember must not be null"
		);
		this.baseToolPlan = baseToolPlan;
		this.planVersion = validatePlanVersion(planVersion);
		this.status = status == null ? ToolPlanStatus.REVIEW : status;
		this.mode = mode == null ? ToolPlanMode.PLAN : mode;
		this.requestedPrompt = requestedPrompt;
		this.rawMarkdown = Objects.requireNonNull(rawMarkdown, "rawMarkdown must not be null");
		this.structuredPlanJson = Objects.requireNonNull(
			structuredPlanJson,
			"structuredPlanJson must not be null"
		);
		this.planSnapshot = Objects.requireNonNull(planSnapshot, "planSnapshot must not be null");
	}

	public void requestApproval() {
		if (!ToolPlanStatus.REVIEW.equals(status)) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_STATUS_TRANSITION_INVALID);
		}
		status = ToolPlanStatus.PENDING;
	}

	public void approve() {
		if (!ToolPlanStatus.PENDING.equals(status)) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_STATUS_TRANSITION_INVALID);
		}
		status = ToolPlanStatus.APPROVED;
	}

	public void reject() {
		if (!ToolPlanStatus.REVIEW.equals(status) && !ToolPlanStatus.PENDING.equals(status)) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_STATUS_TRANSITION_INVALID);
		}
		status = ToolPlanStatus.REJECTED;
	}

	public void supersede() {
		if (!ToolPlanStatus.REVIEW.equals(status) && !ToolPlanStatus.REJECTED.equals(status)) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_STATUS_TRANSITION_INVALID);
		}
		status = ToolPlanStatus.SUPERSEDED;
	}

	public void fail() {
		if (!ToolPlanStatus.REVIEW.equals(status) && !ToolPlanStatus.PENDING.equals(status)) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_STATUS_TRANSITION_INVALID);
		}
		status = ToolPlanStatus.FAILED;
	}

	public boolean canRegenerate() {
		return ToolPlanStatus.REVIEW.equals(status) || ToolPlanStatus.REJECTED.equals(status);
	}

	@PrePersist
	private void prePersist() {
		LocalDateTime now = LocalDateTime.now();
		createdAt = now;
		updatedAt = now;
	}

	@PreUpdate
	private void preUpdate() {
		updatedAt = LocalDateTime.now();
	}

	private Long validatePlanVersion(Long planVersion) {
		if (planVersion == null || planVersion < 1) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_VERSION_INVALID);
		}

		return planVersion;
	}
}
