package com.theseus.api.domain.chat.entity;

import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
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
import jakarta.persistence.PreUpdate;
import jakarta.persistence.Table;
import java.time.LocalDateTime;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(
	name = "chat_sessions",
	indexes = {
		@Index(name = "idx_chat_sessions_project_member", columnList = "project_member_id")
	}
)
@Entity
public class ChatSession {

	@Id
	@GeneratedValue(strategy = GenerationType.IDENTITY)
	private Long id;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "project_id", nullable = false)
	private Project project;

	@ManyToOne(fetch = FetchType.LAZY)
	@JoinColumn(name = "project_member_id", nullable = false)
	private ProjectMember projectMember;

	@Column(length = 150)
	private String title;

	@Column(name = "created_at", nullable = false, updatable = false)
	private LocalDateTime createdAt;

	@Column(name = "updated_at", nullable = false)
	private LocalDateTime updatedAt;

	@Column(name = "closed_at")
	private LocalDateTime closedAt;

	@Builder
	private ChatSession(Project project, ProjectMember projectMember, String title) {
		this.project = project;
		this.projectMember = projectMember;
		this.title = title;
	}

	public void updateTitle(String title) {
		this.title = title;
	}

	public void close(LocalDateTime closedAt) {
		this.closedAt = closedAt == null ? LocalDateTime.now() : closedAt;
	}

	public boolean isClosed() {
		return closedAt != null;
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
