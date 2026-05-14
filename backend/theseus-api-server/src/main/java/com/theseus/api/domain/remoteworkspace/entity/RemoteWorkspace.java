package com.theseus.api.domain.remoteworkspace.entity;

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
	name = "remote_workspaces",
	indexes = {
		@Index(name = "idx_remote_workspaces_project_status", columnList = "project_id, status")
	}
)
@Entity
public class RemoteWorkspace {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "project_id", nullable = false, foreignKey = @ForeignKey(name = "fk_remote_workspaces_project"))
	private Project project;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(
		name = "created_by_project_member_id",
		nullable = false,
		foreignKey = @ForeignKey(name = "fk_remote_workspaces_created_by_project_member")
	)
	private ProjectMember createdByProjectMember;

	@Column(nullable = false, length = 100)
	private String name;

	@Column(nullable = false, length = 255)
	private String host;

	@Column(nullable = false)
	private Integer port;

	@Column(nullable = false, length = 100)
	private String username;

	@Column(length = 500)
	private String password;

	@Column(name = "private_key_path", length = 500)
	private String privateKeyPath;

	@Column(name = "base_path", nullable = false, length = 500)
	private String basePath;

	@Column(name = "allow_write_execution", nullable = false)
	private Boolean allowWriteExecution;

	@Enumerated(EnumType.STRING)
	@Column(nullable = false, length = 30)
	private RemoteWorkspaceStatus status;

	@Column(name = "created_at", nullable = false, updatable = false)
	private LocalDateTime createdAt;

	@Column(name = "updated_at", nullable = false)
	private LocalDateTime updatedAt;

	@Builder
	private RemoteWorkspace(
		Project project,
		ProjectMember createdByProjectMember,
		String name,
		String host,
		Integer port,
		String username,
		String password,
		String privateKeyPath,
		String basePath,
		Boolean allowWriteExecution,
		RemoteWorkspaceStatus status
	) {
		this.project = Objects.requireNonNull(project, "project must not be null");
		this.createdByProjectMember = Objects.requireNonNull(
			createdByProjectMember,
			"createdByProjectMember must not be null"
		);
		this.name = normalizeRequired(name);
		this.host = normalizeRequired(host);
		this.port = Objects.requireNonNull(port, "port must not be null");
		this.username = normalizeRequired(username);
		this.password = normalizeOptional(password);
		this.privateKeyPath = normalizeOptional(privateKeyPath);
		this.basePath = normalizeRequired(basePath);
		this.allowWriteExecution = Boolean.TRUE.equals(allowWriteExecution);
		this.status = status == null ? RemoteWorkspaceStatus.ACTIVE : status;
	}

	public void update(
		String name,
		String host,
		Integer port,
		String username,
		String password,
		String privateKeyPath,
		String basePath,
		Boolean allowWriteExecution
	) {
		if (name != null) {
			this.name = normalizeRequired(name);
		}
		if (host != null) {
			this.host = normalizeRequired(host);
		}
		if (port != null) {
			this.port = port;
		}
		if (username != null) {
			this.username = normalizeRequired(username);
		}
		if (password != null) {
			this.password = normalizeOptional(password);
		}
		if (privateKeyPath != null) {
			this.privateKeyPath = normalizeOptional(privateKeyPath);
		}
		if (basePath != null) {
			this.basePath = normalizeRequired(basePath);
		}
		if (allowWriteExecution != null) {
			this.allowWriteExecution = allowWriteExecution;
		}
	}

	public Boolean isAllowWriteExecution() {
		return Boolean.TRUE.equals(allowWriteExecution);
	}

	public void delete() {
		status = RemoteWorkspaceStatus.DELETED;
	}

	public boolean isDeleted() {
		return RemoteWorkspaceStatus.DELETED.equals(status);
	}

	@PrePersist
	private void prePersist() {
		LocalDateTime now = LocalDateTime.now();
		if (allowWriteExecution == null) {
			allowWriteExecution = false;
		}
		createdAt = now;
		updatedAt = now;
	}

	@PreUpdate
	private void preUpdate() {
		updatedAt = LocalDateTime.now();
	}

	private String normalizeRequired(String value) {
		return Objects.requireNonNull(value, "required value must not be null").trim();
	}

	private String normalizeOptional(String value) {
		if (value == null || value.isBlank()) {
			return null;
		}
		return value.trim();
	}
}
