package com.theseus.api.domain.project.dto.request;

import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectStatus;
import com.theseus.api.domain.user.entity.User;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.Getter;

@Getter
public class ProjectCreateRequest {

	@NotBlank
	@Size(max = 100)
	private String name;

	private String description;

	@NotNull
	private Long adminUserId;

	public Project toEntity(User createdByUser) {
		return Project.builder()
			.name(name)
			.description(description)
			.status(ProjectStatus.ACTIVE)
			.createdByUser(createdByUser)
			.build();
	}
}
