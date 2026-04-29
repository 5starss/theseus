package com.theseus.api.domain.project.dto.response;

import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectStatus;
import java.time.LocalDateTime;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ProjectSummaryResponse {

	private Long projectId;
	private String name;
	private String description;
	private ProjectStatus status;
	private Long projectAdminUserId;
	private String projectAdminEmployeeNumber;
	private String projectAdminName;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;

	public static ProjectSummaryResponse createFrom(Project project) {
		return ProjectSummaryResponse.builder()
			.projectId(project.getId())
			.name(project.getName())
			.description(project.getDescription())
			.status(project.getStatus())
			.projectAdminUserId(project.getProjectAdminUser().getId())
			.projectAdminEmployeeNumber(project.getProjectAdminUser().getEmployeeNumber())
			.projectAdminName(project.getProjectAdminUser().getName())
			.createdAt(project.getCreatedAt())
			.updatedAt(project.getUpdatedAt())
			.build();
	}
}
