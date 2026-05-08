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
import java.time.LocalDateTime;
import java.util.Objects;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
	name = "tool_plan_groups",
	indexes = {
		@Index(name = "idx_tool_plan_groups_project_session", columnList = "project_id, chat_session_id")
	}
)
@Entity
public class ToolPlanGroup {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "project_id", nullable = false, foreignKey = @ForeignKey(name = "fk_tool_plan_groups_project"))
	private Project project;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(
		name = "chat_session_id",
		nullable = false,
		foreignKey = @ForeignKey(name = "fk_tool_plan_groups_chat_session")
	)
	private ChatSession chatSession;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(
		name = "created_by_project_member_id",
		nullable = false,
		foreignKey = @ForeignKey(name = "fk_tool_plan_groups_created_by_project_member")
	)
	private ProjectMember createdByProjectMember;

	@Enumerated(EnumType.STRING)
	@Column(nullable = false, length = 30, columnDefinition = "VARCHAR(30) DEFAULT 'PLANNING'")
	private ToolPlanGroupStatus status;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(
		name = "latest_tool_plan_id",
		foreignKey = @ForeignKey(name = "fk_tool_plan_groups_latest_tool_plan")
	)
	private ToolPlan latestToolPlan;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(
		name = "approved_tool_plan_id",
		foreignKey = @ForeignKey(name = "fk_tool_plan_groups_approved_tool_plan")
	)
	private ToolPlan approvedToolPlan;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "created_tool_id", foreignKey = @ForeignKey(name = "fk_tool_plan_groups_created_tool"))
	private Tool createdTool;

	@Column(name = "created_at", nullable = false, updatable = false)
	private LocalDateTime createdAt;

	@Column(name = "updated_at", nullable = false)
	private LocalDateTime updatedAt;

	@Builder
	private ToolPlanGroup(
		Project project,
		ChatSession chatSession,
		ProjectMember createdByProjectMember,
		ToolPlanGroupStatus status,
		ToolPlan latestToolPlan,
		ToolPlan approvedToolPlan,
		Tool createdTool
	) {
		this.project = Objects.requireNonNull(project, "project must not be null");
		this.chatSession = Objects.requireNonNull(chatSession, "chatSession must not be null");
		this.createdByProjectMember = Objects.requireNonNull(
			createdByProjectMember,
			"createdByProjectMember must not be null"
		);
		this.status = status == null ? ToolPlanGroupStatus.PLANNING : status;
		this.latestToolPlan = latestToolPlan;
		this.approvedToolPlan = approvedToolPlan;
		this.createdTool = createdTool;
	}

	public void markReview(ToolPlan latestToolPlan) {
		validateStatus(
			ToolPlanGroupStatus.PLANNING,
			ToolPlanGroupStatus.REVIEW,
			ToolPlanGroupStatus.REJECTED
		);
		this.latestToolPlan = Objects.requireNonNull(latestToolPlan, "latestToolPlan must not be null");
		status = ToolPlanGroupStatus.REVIEW;
	}

	public void markPending(ToolPlan latestToolPlan) {
		validateStatus(ToolPlanGroupStatus.REVIEW);
		this.latestToolPlan = Objects.requireNonNull(latestToolPlan, "latestToolPlan must not be null");
		status = ToolPlanGroupStatus.PENDING;
	}

	public void approve(ToolPlan approvedToolPlan) {
		validateStatus(ToolPlanGroupStatus.PENDING);
		this.approvedToolPlan = Objects.requireNonNull(approvedToolPlan, "approvedToolPlan must not be null");
		this.latestToolPlan = approvedToolPlan;
		status = ToolPlanGroupStatus.APPROVED;
	}

	public void startBuilding() {
		if (!ToolPlanGroupStatus.APPROVED.equals(status)) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_STATUS_TRANSITION_INVALID);
		}
		status = ToolPlanGroupStatus.BUILDING;
	}

	public void completeBuild(Tool createdTool) {
		if (!ToolPlanGroupStatus.BUILDING.equals(status)) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_STATUS_TRANSITION_INVALID);
		}
		this.createdTool = Objects.requireNonNull(createdTool, "createdTool must not be null");
		status = ToolPlanGroupStatus.BUILT;
	}

	public void reject() {
		validateStatus(ToolPlanGroupStatus.PENDING);
		status = ToolPlanGroupStatus.REJECTED;
	}

	public void cancel() {
		validateStatus(
			ToolPlanGroupStatus.PLANNING,
			ToolPlanGroupStatus.REVIEW,
			ToolPlanGroupStatus.PENDING,
			ToolPlanGroupStatus.REJECTED
		);
		status = ToolPlanGroupStatus.CANCELLED;
	}

	public void fail() {
		validateMutableBuildFailure();
		status = ToolPlanGroupStatus.FAILED;
	}

	public boolean isFinished() {
		return ToolPlanGroupStatus.BUILT.equals(status)
			|| ToolPlanGroupStatus.CANCELLED.equals(status)
			|| ToolPlanGroupStatus.FAILED.equals(status);
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

	private void validateStatus(ToolPlanGroupStatus... allowedStatuses) {
		for (ToolPlanGroupStatus allowedStatus : allowedStatuses) {
			if (allowedStatus.equals(status)) {
				return;
			}
		}

		throw BusinessException.of(ErrorCode.TOOL_PLAN_STATUS_TRANSITION_INVALID);
	}

	private void validateMutableBuildFailure() {
		if (ToolPlanGroupStatus.BUILT.equals(status)
			|| ToolPlanGroupStatus.CANCELLED.equals(status)
			|| ToolPlanGroupStatus.FAILED.equals(status)) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_STATUS_TRANSITION_INVALID);
		}
	}
}
