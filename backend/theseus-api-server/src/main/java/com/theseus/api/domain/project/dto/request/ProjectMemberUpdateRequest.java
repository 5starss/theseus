package com.theseus.api.domain.project.dto.request;

import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.entity.ProjectRole;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;

@Getter
public class ProjectMemberUpdateRequest {

	@NotNull
	private ProjectRole projectRole;

	@NotNull
	@Min(1)
	private Integer accessLevel;

	@NotNull
	private Boolean canCreateTool;

	@NotNull
	private Boolean canUseTool;

	@NotNull
	private Boolean canUpdateTool;

	@NotNull
	private Boolean canDeleteTool;

	private ProjectMemberStatus status;
}
