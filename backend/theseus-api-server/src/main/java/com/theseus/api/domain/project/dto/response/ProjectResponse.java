package com.theseus.api.domain.project.dto.response;

import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectStatus;
import java.time.LocalDateTime;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ProjectResponse {

	private Long projectId;
	private String name;
	private String description;
	private ProjectStatus status;
	private Long createdByUserId;
	private String createdByUserName;
	private Long projectAdminUserId;
	private String projectAdminEmployeeNumber;
	private String projectAdminName;
	private Long adminProjectMemberId;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;

	public static ProjectResponse createFrom(Project project) {
		return createOf(project, null);
	}

	public static ProjectResponse createOf(Project project, ProjectMember adminProjectMember) {
		return ProjectResponse.builder()
			.projectId(project.getId())
			.name(project.getName())
			.description(project.getDescription())
			.status(project.getStatus())
			.createdByUserId(project.getCreatedByUser().getId())
			.createdByUserName(project.getCreatedByUser().getName())
			.projectAdminUserId(project.getProjectAdminUser().getId())
			.projectAdminEmployeeNumber(project.getProjectAdminUser().getEmployeeNumber())
			.projectAdminName(project.getProjectAdminUser().getName())
			.adminProjectMemberId(adminProjectMember == null ? null : adminProjectMember.getId())
			.createdAt(project.getCreatedAt())
			.updatedAt(project.getUpdatedAt())
			.build();
	}
}
