package com.theseus.api.domain.project.dto.response;

import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.entity.ProjectStatus;
import java.time.LocalDateTime;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class MyProjectResponse {

	private Long projectId;
	private String name;
	private String description;
	private ProjectStatus projectStatus;
	private ProjectRole projectRole;
	private ProjectMemberStatus memberStatus;
	private Long projectAdminUserId;
	private String projectAdminEmployeeNumber;
	private String projectAdminName;
	private Boolean isProjectAdminUser;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;

	public static MyProjectResponse createFrom(ProjectMember projectMember) {
		Project project = projectMember.getProject();
		boolean isProjectAdminUser = project.getProjectAdminUser().getId().equals(projectMember.getUser().getId());

		return MyProjectResponse.builder()
			.projectId(project.getId())
			.name(project.getName())
			.description(project.getDescription())
			.projectStatus(project.getStatus())
			.projectRole(projectMember.getProjectRole())
			.memberStatus(projectMember.getStatus())
			.projectAdminUserId(project.getProjectAdminUser().getId())
			.projectAdminEmployeeNumber(project.getProjectAdminUser().getEmployeeNumber())
			.projectAdminName(project.getProjectAdminUser().getName())
			.isProjectAdminUser(isProjectAdminUser)
			.createdAt(project.getCreatedAt())
			.updatedAt(project.getUpdatedAt())
			.build();
	}
}
