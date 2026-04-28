package com.theseus.api.domain.project.dto.request;

import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.user.entity.User;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;

@Getter
public class ProjectMemberCreateRequest {

	@NotNull
	private Long userId;

	private ProjectRole projectRole = ProjectRole.MEMBER;

	@Min(1)
	private Integer accessLevel = 1;

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
