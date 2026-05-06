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
	name = "tools",
	uniqueConstraints = {
		@UniqueConstraint(name = "uk_tools_project_file_name", columnNames = {"project_id", "file_name"})
	},
	indexes = {
		@Index(name = "idx_tools_chat_session_status", columnList = "chat_session_id, status"),
		@Index(name = "idx_tools_project_status", columnList = "project_id, status")
	}
)
@Entity
public class Tool {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "project_id", nullable = false, foreignKey = @ForeignKey(name = "fk_tools_project"))
	private Project project;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "chat_session_id", nullable = false, foreignKey = @ForeignKey(name = "fk_tools_chat_session"))
	private ChatSession chatSession;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(
		name = "created_by_project_member_id",
		nullable = false,
		foreignKey = @ForeignKey(name = "fk_tools_created_by_project_member")
	)
	private ProjectMember createdByProjectMember;

	@Column(name = "file_name", nullable = false, length = 120)
	private String fileName;

	@Column(name = "display_name", length = 30)
	private String displayName;

	@Column(name = "display_description", columnDefinition = "TEXT")
	private String displayDescription;

	@Enumerated(EnumType.STRING)
	@Column(nullable = false, length = 30, columnDefinition = "VARCHAR(30) DEFAULT 'DRAFT'")
	private ToolStatus status;

	@Enumerated(EnumType.STRING)
	@Column(name = "draft_phase", nullable = false, length = 30, columnDefinition = "VARCHAR(30) DEFAULT 'PLAN'")
	private ToolDraftPhase draftPhase;

	@Column(name = "draft_version", nullable = false, columnDefinition = "BIGINT DEFAULT 0")
	private Long draftVersion;

	@Column(name = "tool_grade", columnDefinition = "INT UNSIGNED")
	private Integer toolGrade;

	@Column(name = "raw_markdown", columnDefinition = "LONGTEXT")
	private String rawMarkdown;

	@Column(name = "structured_plan_json", columnDefinition = "LONGTEXT")
	private String structuredPlanJson;

	@Column(name = "draft_snapshot", columnDefinition = "LONGTEXT")
	private String draftSnapshot;

	@Column(name = "created_at", nullable = false, updatable = false)
	private LocalDateTime createdAt;

	@Column(name = "updated_at", nullable = false)
	private LocalDateTime updatedAt;

	@Builder
	private Tool(
		Project project,
		ChatSession chatSession,
		ProjectMember createdByProjectMember,
		String fileName,
		String displayName,
		String displayDescription,
		ToolStatus status,
		ToolDraftPhase draftPhase,
		Long draftVersion,
		Integer toolGrade,
		String rawMarkdown,
		String structuredPlanJson,
		String draftSnapshot
	) {
		this.project = Objects.requireNonNull(project, "project must not be null");
		this.chatSession = Objects.requireNonNull(chatSession, "chatSession must not be null");
		this.createdByProjectMember = Objects.requireNonNull(
			createdByProjectMember,
			"createdByProjectMember must not be null"
		);
		this.fileName = validateFileName(fileName);
		this.displayName = displayName;
		this.displayDescription = displayDescription;
		this.status = status == null ? ToolStatus.DRAFT : status;
		this.draftPhase = draftPhase == null ? ToolDraftPhase.PLAN : draftPhase;
		this.draftVersion = draftVersion == null ? 0L : draftVersion;
		this.toolGrade = toolGrade;
		this.rawMarkdown = rawMarkdown;
		this.structuredPlanJson = structuredPlanJson;
		this.draftSnapshot = draftSnapshot;
	}

	public void updateDraft(
		String rawMarkdown,
		String structuredPlanJson,
		String draftSnapshot,
		ToolDraftPhase draftPhase
	) {
		if (rawMarkdown != null) {
			this.rawMarkdown = rawMarkdown;
		}
		if (structuredPlanJson != null) {
			this.structuredPlanJson = structuredPlanJson;
		}
		if (draftSnapshot != null) {
			this.draftSnapshot = draftSnapshot;
		}
		if (draftPhase != null) {
			this.draftPhase = draftPhase;
		}
	}

	public void startRegeneration() {
		status = ToolStatus.DRAFT;
		draftPhase = ToolDraftPhase.PLAN;
	}

	public void completeDraftReview(
		String rawMarkdown,
		String structuredPlanJson,
		String draftSnapshot
	) {
		updateDraft(rawMarkdown, structuredPlanJson, draftSnapshot, ToolDraftPhase.REVIEW);
		increaseDraftVersion();
	}

	public void markAsPlan() {
		draftPhase = ToolDraftPhase.PLAN;
	}

	public void markAsReview() {
		draftPhase = ToolDraftPhase.REVIEW;
	}

	public void requestApproval() {
		status = ToolStatus.PENDING;
	}

	public void approve(Integer toolGrade) {
		status = ToolStatus.APPROVED;
		this.toolGrade = toolGrade;
	}

	public void reject() {
		status = ToolStatus.REJECTED;
		draftPhase = ToolDraftPhase.REVIEW;
	}

	public void updateDisplayInfo(String displayName, String displayDescription, Integer toolGrade) {
		if (displayName != null) {
			this.displayName = displayName;
		}
		if (displayDescription != null) {
			this.displayDescription = displayDescription;
		}
		if (toolGrade != null) {
			this.toolGrade = toolGrade;
		}
	}

	public void delete() {
		status = ToolStatus.DELETED;
	}

	public boolean isDraft() {
		return ToolStatus.DRAFT.equals(status);
	}

	public boolean isPending() {
		return ToolStatus.PENDING.equals(status);
	}

	public boolean isApproved() {
		return ToolStatus.APPROVED.equals(status);
	}

	public boolean isRejected() {
		return ToolStatus.REJECTED.equals(status);
	}

	public boolean isDeleted() {
		return ToolStatus.DELETED.equals(status);
	}

	public boolean canRequestApproval() {
		return ToolStatus.DRAFT.equals(status) && ToolDraftPhase.REVIEW.equals(draftPhase);
	}

	public boolean canRegenerate() {
		return ToolStatus.DRAFT.equals(status) || ToolStatus.REJECTED.equals(status);
	}

	public boolean isAccessibleWithAccessLevel(Integer accessLevel) {
		if (toolGrade == null) {
			return true;
		}

		return accessLevel != null && accessLevel >= toolGrade;
	}

	@PrePersist
	private void prePersist() {
		LocalDateTime now = LocalDateTime.now();
		createdAt = now;
		updatedAt = now;
		if (draftVersion == null) {
			draftVersion = 0L;
		}
	}

	@PreUpdate
	private void preUpdate() {
		updatedAt = LocalDateTime.now();
	}

	private String validateFileName(String fileName) {
		if (fileName == null || fileName.isBlank()) {
			throw BusinessException.of(ErrorCode.TOOL_FILE_NAME_REQUIRED);
		}

		return fileName;
	}

	private void increaseDraftVersion() {
		draftVersion = draftVersion == null ? 1L : draftVersion + 1;
	}
}
