package com.theseus.api.domain.project.entity;

import com.theseus.api.domain.user.entity.User;
import jakarta.persistence.Column;
import jakarta.persistence.Convert;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.PrePersist;
import jakarta.persistence.PreUpdate;
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
	name = "project_members",
	uniqueConstraints = {
		@UniqueConstraint(name = "uk_project_members_project_user", columnNames = {"project_id", "user_id"})
	}
)
@Entity
public class ProjectMember {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "project_id", nullable = false)
	private Project project;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "user_id", nullable = false)
	private User user;

	@Enumerated(EnumType.STRING)
	@Column(name = "project_role", nullable = false, length = 30)
	private ProjectRole projectRole;

	@Column(name = "access_level", nullable = false)
	private Integer accessLevel;

	@Column(name = "can_create_tool", nullable = false)
	private Boolean canCreateTool;

	@Column(name = "can_use_tool", nullable = false)
	private Boolean canUseTool;

	@Column(name = "can_update_tool", nullable = false)
	private Boolean canUpdateTool;

	@Column(name = "can_delete_tool", nullable = false)
	private Boolean canDeleteTool;

	@Convert(converter = ProjectMemberStatusConverter.class)
	@Column(nullable = false, length = 30)
	private ProjectMemberStatus status;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "created_by_user_id")
	private User createdByUser;

	@Column(name = "created_at", nullable = false, updatable = false)
	private LocalDateTime createdAt;

	@Column(name = "updated_at", nullable = false)
	private LocalDateTime updatedAt;

	@Builder
	private ProjectMember(
		Project project,
		User user,
		ProjectRole projectRole,
		Integer accessLevel,
		Boolean canCreateTool,
		Boolean canUseTool,
		Boolean canUpdateTool,
		Boolean canDeleteTool,
		ProjectMemberStatus status,
		User createdByUser
	) {
		this.project = project;
		this.user = user;
		this.projectRole = projectRole == null ? ProjectRole.MEMBER : projectRole;
		this.accessLevel = accessLevel == null ? 1 : accessLevel;
		this.canCreateTool = canCreateTool != null && canCreateTool;
		this.canUseTool = canUseTool == null || canUseTool;
		this.canUpdateTool = canUpdateTool != null && canUpdateTool;
		this.canDeleteTool = canDeleteTool != null && canDeleteTool;
		this.status = status == null ? ProjectMemberStatus.IN_PROGRESS : status;
		this.createdByUser = createdByUser;
	}

	public void update(
		ProjectRole projectRole,
		Integer accessLevel,
		Boolean canCreateTool,
		Boolean canUseTool,
		Boolean canUpdateTool,
		Boolean canDeleteTool,
		ProjectMemberStatus status
	) {
		if (projectRole != null) {
			this.projectRole = projectRole;
		}
		if (accessLevel != null) {
			this.accessLevel = accessLevel;
		}
		if (canCreateTool != null) {
			this.canCreateTool = canCreateTool;
		}
		if (canUseTool != null) {
			this.canUseTool = canUseTool;
		}
		if (canUpdateTool != null) {
			this.canUpdateTool = canUpdateTool;
		}
		if (canDeleteTool != null) {
			this.canDeleteTool = canDeleteTool;
		}
		if (status != null) {
			this.status = status;
		}
	}

	public void assignProjectAdminRole() {
		projectRole = ProjectRole.ADMIN;
		status = ProjectMemberStatus.IN_PROGRESS;
		canCreateTool = true;
		canUseTool = true;
		canUpdateTool = true;
		canDeleteTool = true;
	}

	public void complete() {
		this.status = ProjectMemberStatus.COMPLETED;
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
}
