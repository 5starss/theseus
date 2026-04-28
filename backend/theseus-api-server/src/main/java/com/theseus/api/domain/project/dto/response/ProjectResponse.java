package com.theseus.api.domain.project.dto.response;

import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectStatus;
import java.time.LocalDateTime;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ProjectResponse {

	private Long id;
	private String name;
	private String description;
	private ProjectStatus status;
	private Long createdByUserId;
	private String createdByUserName;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;

	public static ProjectResponse createFrom(Project project) {
		return ProjectResponse.builder()
			.id(project.getId())
			.name(project.getName())
			.description(project.getDescription())
			.status(project.getStatus())
			.createdByUserId(project.getCreatedByUser().getId())
			.createdByUserName(project.getCreatedByUser().getName())
			.createdAt(project.getCreatedAt())
			.updatedAt(project.getUpdatedAt())
			.build();
	}
}
