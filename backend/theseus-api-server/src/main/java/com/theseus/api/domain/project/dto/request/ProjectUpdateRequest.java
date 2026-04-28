package com.theseus.api.domain.project.dto.request;

import com.theseus.api.domain.project.entity.ProjectStatus;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Getter;

@Getter
public class ProjectUpdateRequest {

	@NotBlank
	@Size(max = 100)
	private String name;

	private String description;

	private ProjectStatus status;
}
