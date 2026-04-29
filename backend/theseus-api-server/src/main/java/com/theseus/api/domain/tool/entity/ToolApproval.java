package com.theseus.api.domain.tool.entity;

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
	name = "tool_approvals",
	uniqueConstraints = {
		@UniqueConstraint(name = "uk_tool_approvals_tool_request", columnNames = {"tool_id", "request_number"})
	},
	indexes = {
		@Index(name = "idx_tool_approvals_tool_status", columnList = "tool_id, approval_status")
	}
)
@Entity
public class ToolApproval {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "tool_id", nullable = false, foreignKey = @ForeignKey(name = "fk_tool_approvals_tool"))
	private Tool tool;

	@Column(name = "request_number", nullable = false)
	private Integer requestNumber;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(
		name = "requested_by_project_member_id",
		nullable = false,
		foreignKey = @ForeignKey(name = "fk_tool_approvals_requested_by_project_member")
	)
	private ProjectMember requestedByProjectMember;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(
		name = "reviewed_by_project_member_id",
		foreignKey = @ForeignKey(name = "fk_tool_approvals_reviewed_by_project_member")
	)
	private ProjectMember reviewedByProjectMember;

	@Enumerated(EnumType.STRING)
	@Column(name = "approval_status", nullable = false, length = 30, columnDefinition = "VARCHAR(30) DEFAULT 'PENDING'")
	private ToolApprovalStatus approvalStatus;

	@Column(name = "review_feedback", columnDefinition = "TEXT")
	private String reviewFeedback;

	@Column(name = "requested_at", nullable = false, updatable = false)
	private LocalDateTime requestedAt;

	@Column(name = "reviewed_at")
	private LocalDateTime reviewedAt;

	@Builder
	private ToolApproval(
		Tool tool,
		Integer requestNumber,
		ProjectMember requestedByProjectMember
	) {
		this.tool = Objects.requireNonNull(tool, "tool must not be null");
		this.requestNumber = validateRequestNumber(requestNumber);
		this.requestedByProjectMember = Objects.requireNonNull(
			requestedByProjectMember,
			"requestedByProjectMember must not be null"
		);
		this.approvalStatus = ToolApprovalStatus.PENDING;
	}

	public void approve(ProjectMember reviewedByProjectMember, String reviewFeedback) {
		approve(reviewedByProjectMember, reviewFeedback, LocalDateTime.now());
	}

	void approve(ProjectMember reviewedByProjectMember, String reviewFeedback, LocalDateTime reviewedAt) {
		review(ToolApprovalStatus.APPROVED, reviewedByProjectMember, reviewFeedback, reviewedAt);
	}

	public void reject(ProjectMember reviewedByProjectMember, String reviewFeedback) {
		reject(reviewedByProjectMember, reviewFeedback, LocalDateTime.now());
	}

	void reject(ProjectMember reviewedByProjectMember, String reviewFeedback, LocalDateTime reviewedAt) {
		review(ToolApprovalStatus.REJECTED, reviewedByProjectMember, reviewFeedback, reviewedAt);
	}

	public boolean isPending() {
		return ToolApprovalStatus.PENDING.equals(approvalStatus);
	}

	public boolean isApproved() {
		return ToolApprovalStatus.APPROVED.equals(approvalStatus);
	}

	public boolean isRejected() {
		return ToolApprovalStatus.REJECTED.equals(approvalStatus);
	}

	public boolean isReviewed() {
		return reviewedAt != null;
	}

	@PrePersist
	private void prePersist() {
		if (requestedAt == null) {
			requestedAt = LocalDateTime.now();
		}
	}

	private void review(
		ToolApprovalStatus approvalStatus,
		ProjectMember reviewedByProjectMember,
		String reviewFeedback,
		LocalDateTime reviewedAt
	) {
		validatePending();

		this.approvalStatus = approvalStatus;
		this.reviewedByProjectMember = Objects.requireNonNull(
			reviewedByProjectMember,
			"reviewedByProjectMember must not be null"
		);
		this.reviewFeedback = reviewFeedback;
		this.reviewedAt = Objects.requireNonNull(reviewedAt, "reviewedAt must not be null");
	}

	private void validatePending() {
		if (!isPending()) {
			throw new IllegalStateException("tool approval is already reviewed");
		}
	}

	private Integer validateRequestNumber(Integer requestNumber) {
		if (requestNumber == null || requestNumber < 1) {
			throw new IllegalArgumentException("requestNumber must be greater than zero");
		}

		return requestNumber;
	}
}
