package com.theseus.api.domain.project.dto.request;

import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.entity.ProjectRole;
import jakarta.validation.constraints.Min;
import lombok.Getter;

@Getter
public class ProjectMemberUpdateRequest {

	private ProjectRole projectRole;

	@Min(1)
	private Integer accessLevel;

	private Boolean canCreateTool;

	private Boolean canUseTool;

	private Boolean canUpdateTool;

	private Boolean canDeleteTool;

	private ProjectMemberStatus status;
}
