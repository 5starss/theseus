package com.theseus.api.domain.tool.entity;

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
	name = "tool_usage_logs",
	indexes = {
		@Index(name = "idx_tool_usage_logs_project_used_at", columnList = "project_id, used_at"),
		@Index(name = "idx_tool_usage_logs_project_status", columnList = "project_id, status")
	}
)
@Entity
public class ToolUsageLog {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "project_id", nullable = false, foreignKey = @ForeignKey(name = "fk_tool_usage_logs_project"))
	private Project project;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "tool_id", nullable = false, foreignKey = @ForeignKey(name = "fk_tool_usage_logs_tool"))
	private Tool tool;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(
		name = "used_by_project_member_id",
		nullable = false,
		foreignKey = @ForeignKey(name = "fk_tool_usage_logs_used_by_project_member")
	)
	private ProjectMember usedByProjectMember;

	@Enumerated(EnumType.STRING)
	@Column(nullable = false, length = 20)
	private ToolUsageStatus status;

	@Column(name = "used_at", nullable = false)
	private LocalDateTime usedAt;

	@Column(name = "error_message", columnDefinition = "TEXT")
	private String errorMessage;

	@Builder
	private ToolUsageLog(
		Project project,
		Tool tool,
		ProjectMember usedByProjectMember,
		ToolUsageStatus status,
		LocalDateTime usedAt,
		String errorMessage
	) {
		this.project = Objects.requireNonNull(project, "project must not be null");
		this.tool = Objects.requireNonNull(tool, "tool must not be null");
		this.usedByProjectMember = Objects.requireNonNull(usedByProjectMember, "usedByProjectMember must not be null");
		this.status = Objects.requireNonNull(status, "status must not be null");
		this.usedAt = usedAt;
		this.errorMessage = errorMessage;
	}

	@PrePersist
	private void prePersist() {
		if (usedAt == null) {
			usedAt = LocalDateTime.now();
		}
	}
}
