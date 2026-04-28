package com.theseus.api.domain.project.dto.request;

import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectStatus;
import com.theseus.api.domain.user.entity.User;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Getter;

@Getter
public class ProjectCreateRequest {

	@NotBlank
	@Size(max = 100)
	private String name;

	private String description;

	@NotBlank
	@Size(max = 50)
	private String adminEmployeeNumber;

	@NotBlank
	@Size(max = 100)
	private String adminName;

	public Project toEntity(User createdByUser, User projectAdminUser) {
		return Project.builder()
			.name(name)
			.description(description)
			.status(ProjectStatus.ACTIVE)
			.createdByUser(createdByUser)
			.projectAdminUser(projectAdminUser)
			.build();
	}
}
