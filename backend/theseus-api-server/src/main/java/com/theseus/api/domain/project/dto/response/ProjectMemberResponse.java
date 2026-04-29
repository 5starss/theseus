package com.theseus.api.domain.project.dto.response;

import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.entity.ProjectRole;
import java.time.LocalDateTime;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ProjectMemberResponse {

	private Long projectMemberId;
	private Long projectId;
	private String projectName;
	private Long userId;
	private String employeeNumber;
	private String name;
	private ProjectRole projectRole;
	private Integer accessLevel;
	private Boolean canCreateTool;
	private Boolean canUseTool;
	private Boolean canUpdateTool;
	private Boolean canDeleteTool;
	private ProjectMemberStatus status;
	private Boolean isProjectAdminUser;
	private Long createdByUserId;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;

	public static ProjectMemberResponse createFrom(ProjectMember projectMember) {
		return createOf(projectMember, false);
	}

	public static ProjectMemberResponse createOf(ProjectMember projectMember, boolean isProjectAdminUser) {
		return ProjectMemberResponse.builder()
			.projectMemberId(projectMember.getId())
			.projectId(projectMember.getProject().getId())
			.projectName(projectMember.getProject().getName())
			.userId(projectMember.getUser().getId())
			.employeeNumber(projectMember.getUser().getEmployeeNumber())
			.name(projectMember.getUser().getName())
			.projectRole(projectMember.getProjectRole())
			.accessLevel(projectMember.getAccessLevel())
			.canCreateTool(projectMember.getCanCreateTool())
			.canUseTool(projectMember.getCanUseTool())
			.canUpdateTool(projectMember.getCanUpdateTool())
			.canDeleteTool(projectMember.getCanDeleteTool())
			.status(projectMember.getStatus())
			.isProjectAdminUser(isProjectAdminUser)
			.createdByUserId(projectMember.getCreatedByUser() == null ? null : projectMember.getCreatedByUser().getId())
			.createdAt(projectMember.getCreatedAt())
			.updatedAt(projectMember.getUpdatedAt())
			.build();
	}
}
