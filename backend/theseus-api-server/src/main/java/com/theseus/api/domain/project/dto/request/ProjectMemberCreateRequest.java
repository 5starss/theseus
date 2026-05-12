package com.theseus.api.domain.project.dto.request;

import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectAccessLevelPolicy;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.user.entity.User;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import lombok.Getter;

@Getter
public class ProjectMemberCreateRequest {

	@NotBlank
	private String employeeNumber;

	private ProjectRole projectRole = ProjectRole.MEMBER;

	@Min(1)
	private Integer accessLevel = ProjectAccessLevelPolicy.DEFAULT_MEMBER_ACCESS_LEVEL;

	private Boolean canCreateTool = false;
	private Boolean canUseTool = true;
	private Boolean canUpdateTool = false;
	private Boolean canDeleteTool = false;

	public ProjectMember toEntity(Project project, User user, User createdByUser) {
		return ProjectMember.builder()
			.project(project)
			.user(user)
			.projectRole(projectRole)
			.accessLevel(accessLevel)
			.canCreateTool(canCreateTool)
			.canUseTool(canUseTool)
			.canUpdateTool(canUpdateTool)
			.canDeleteTool(canDeleteTool)
			.status(ProjectMemberStatus.IN_PROGRESS)
			.createdByUser(createdByUser)
			.build();
	}
}
