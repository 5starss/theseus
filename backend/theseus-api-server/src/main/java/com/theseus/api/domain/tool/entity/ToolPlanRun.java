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
	name = "tool_plan_runs",
	uniqueConstraints = {
		@UniqueConstraint(name = "uk_tool_plan_runs_run_id", columnNames = "run_id")
	},
	indexes = {
		@Index(name = "idx_tool_plan_runs_project_session_status", columnList = "project_id, chat_session_id, status")
	}
)
@Entity
public class ToolPlanRun {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@Column(name = "run_id", nullable = false, length = 64)
	private String runId;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "project_id", nullable = false, foreignKey = @ForeignKey(name = "fk_tool_plan_runs_project"))
	private Project project;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(
		name = "chat_session_id",
		nullable = false,
		foreignKey = @ForeignKey(name = "fk_tool_plan_runs_chat_session")
	)
	private ChatSession chatSession;

	@Enumerated(EnumType.STRING)
	@Column(name = "request_type", nullable = false, length = 30)
	private ToolPlanRunRequestType requestType;

	@Enumerated(EnumType.STRING)
	@Column(nullable = false, length = 30, columnDefinition = "VARCHAR(30) DEFAULT 'PLAN'")
	private ToolPlanMode mode;

	@Enumerated(EnumType.STRING)
	@Column(nullable = false, length = 30, columnDefinition = "VARCHAR(30) DEFAULT 'REQUESTED'")
	private ToolPlanRunStatus status;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(
		name = "requested_by_project_member_id",
		nullable = false,
		foreignKey = @ForeignKey(name = "fk_tool_plan_runs_requested_by_project_member")
	)
	private ProjectMember requestedByProjectMember;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(
		name = "base_tool_plan_id",
		foreignKey = @ForeignKey(name = "fk_tool_plan_runs_base_tool_plan")
	)
	private ToolPlan baseToolPlan;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(
		name = "result_tool_plan_id",
		foreignKey = @ForeignKey(name = "fk_tool_plan_runs_result_tool_plan")
	)
	private ToolPlan resultToolPlan;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "plan_group_id", foreignKey = @ForeignKey(name = "fk_tool_plan_runs_group"))
	private ToolPlanGroup planGroup;

	@Column(name = "user_message_id")
	private Long userMessageId;

	@Column(name = "request_payload_json", columnDefinition = "LONGTEXT")
	private String requestPayloadJson;

	@Column(name = "history_snapshot_json", columnDefinition = "LONGTEXT")
	private String historySnapshotJson;

	@Column(name = "last_event_type", length = 80)
	private String lastEventType;

	@Column(name = "last_event_sequence")
	private Long lastEventSequence;

	@Column(name = "error_code", length = 120)
	private String errorCode;

	@Column(name = "error_message", columnDefinition = "TEXT")
	private String errorMessage;

	@Column(name = "requested_at", nullable = false, updatable = false)
	private LocalDateTime requestedAt;

	@Column(name = "completed_at")
	private LocalDateTime completedAt;

	@Column(name = "created_at", nullable = false, updatable = false)
	private LocalDateTime createdAt;

	@Column(name = "updated_at", nullable = false)
	private LocalDateTime updatedAt;

	@Builder
	private ToolPlanRun(
		String runId,
		Project project,
		ChatSession chatSession,
		ToolPlanRunRequestType requestType,
		ToolPlanMode mode,
		ToolPlanRunStatus status,
		ProjectMember requestedByProjectMember,
		ToolPlan baseToolPlan,
		ToolPlan resultToolPlan,
		ToolPlanGroup planGroup,
		Long userMessageId,
		String requestPayloadJson,
		String historySnapshotJson,
		LocalDateTime requestedAt
	) {
		this.runId = validateRunId(runId);
		this.project = Objects.requireNonNull(project, "project must not be null");
		this.chatSession = Objects.requireNonNull(chatSession, "chatSession must not be null");
		this.requestType = Objects.requireNonNull(requestType, "requestType must not be null");
		this.mode = mode == null ? ToolPlanMode.PLAN : mode;
		this.status = status == null ? ToolPlanRunStatus.REQUESTED : status;
		this.requestedByProjectMember = Objects.requireNonNull(
			requestedByProjectMember,
			"requestedByProjectMember must not be null"
		);
		this.baseToolPlan = baseToolPlan;
		this.resultToolPlan = resultToolPlan;
		this.planGroup = planGroup;
		this.userMessageId = userMessageId;
		this.requestPayloadJson = requestPayloadJson;
		this.historySnapshotJson = historySnapshotJson;
		this.requestedAt = requestedAt == null ? LocalDateTime.now() : requestedAt;
	}

	public void startGenerating() {
		validateNotFinished();
		status = ToolPlanRunStatus.GENERATING;
	}

	public void startGeneratingIfRequested() {
		validateNotFinished();
		if (ToolPlanRunStatus.REQUESTED.equals(status)) {
			status = ToolPlanRunStatus.GENERATING;
		}
	}

	public void complete(ToolPlan resultToolPlan, LocalDateTime completedAt) {
		validateNotFinished();
		this.resultToolPlan = Objects.requireNonNull(resultToolPlan, "resultToolPlan must not be null");
		this.planGroup = resultToolPlan.getPlanGroup();
		this.status = ToolPlanRunStatus.COMPLETED;
		this.completedAt = Objects.requireNonNull(completedAt, "completedAt must not be null");
		clearError();
	}

	public void fail(String errorCode, String errorMessage, LocalDateTime completedAt) {
		validateNotFinished();
		this.status = ToolPlanRunStatus.FAILED;
		this.errorCode = errorCode;
		this.errorMessage = errorMessage;
		this.completedAt = Objects.requireNonNull(completedAt, "completedAt must not be null");
	}

	public void skip(String errorCode, String errorMessage, LocalDateTime completedAt) {
		validateNotFinished();
		this.status = ToolPlanRunStatus.SKIPPED;
		this.errorCode = errorCode;
		this.errorMessage = errorMessage;
		this.completedAt = Objects.requireNonNull(completedAt, "completedAt must not be null");
	}

	public void attachUserMessageId(Long userMessageId) {
		validateNotFinished();
		this.userMessageId = userMessageId;
	}

	public void attachRequestPayload(String requestPayloadJson, String historySnapshotJson) {
		validateNotFinished();
		this.requestPayloadJson = requestPayloadJson;
		this.historySnapshotJson = historySnapshotJson;
	}

	public void updateLastEvent(String eventType, Long eventSequence) {
		this.lastEventType = eventType;
		if (eventSequence != null) {
			this.lastEventSequence = eventSequence;
		}
	}

	public boolean hasProcessedEventSequence(Long eventSequence) {
		return eventSequence != null
			&& lastEventSequence != null
			&& eventSequence <= lastEventSequence;
	}

	public boolean isFinished() {
		return ToolPlanRunStatus.COMPLETED.equals(status)
			|| ToolPlanRunStatus.FAILED.equals(status)
			|| ToolPlanRunStatus.SKIPPED.equals(status);
	}

	@PrePersist
	private void prePersist() {
		LocalDateTime now = LocalDateTime.now();
		createdAt = now;
		updatedAt = now;
		if (requestedAt == null) {
			requestedAt = now;
		}
	}

	@PreUpdate
	private void preUpdate() {
		updatedAt = LocalDateTime.now();
	}

	private String validateRunId(String runId) {
		if (runId == null || runId.isBlank()) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_RUN_ID_REQUIRED);
		}

		return runId;
	}

	private void validateNotFinished() {
		if (isFinished()) {
			throw BusinessException.of(ErrorCode.TOOL_PLAN_RUN_ALREADY_FINISHED);
		}
	}

	private void clearError() {
		errorCode = null;
		errorMessage = null;
	}
}
