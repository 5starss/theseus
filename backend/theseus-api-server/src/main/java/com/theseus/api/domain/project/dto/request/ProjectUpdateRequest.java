package com.theseus.api.domain.project.dto.request;

import com.theseus.api.domain.project.entity.ProjectStatus;
import jakarta.validation.constraints.Size;
import lombok.Getter;

@Getter
public class ProjectUpdateRequest {

	@Size(max = 100)
	private String name;

	private String description;

	private ProjectStatus status;

	@Size(max = 50)
	private String adminEmployeeNumber;

	@Size(max = 100)
	private String adminName;

	public boolean hasProjectAdminUpdate() {
		return adminEmployeeNumber != null || adminName != null;
	}
}
