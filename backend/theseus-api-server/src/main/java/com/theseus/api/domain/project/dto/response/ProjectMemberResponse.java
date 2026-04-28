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

	private Long id;
	private Long projectId;
	private String projectName;
	private Long userId;
	private String employeeNumber;
	private String userName;
	private ProjectRole projectRole;
	private Integer accessLevel;
	private Boolean canCreateTool;
	private Boolean canUseTool;
	private Boolean canUpdateTool;
	private Boolean canDeleteTool;
	private ProjectMemberStatus status;
	private Long createdByUserId;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;

	public static ProjectMemberResponse createFrom(ProjectMember projectMember) {
		return ProjectMemberResponse.builder()
			.id(projectMember.getId())
			.projectId(projectMember.getProject().getId())
			.projectName(projectMember.getProject().getName())
			.userId(projectMember.getUser().getId())
			.employeeNumber(projectMember.getUser().getEmployeeNumber())
			.userName(projectMember.getUser().getName())
			.projectRole(projectMember.getProjectRole())
			.accessLevel(projectMember.getAccessLevel())
			.canCreateTool(projectMember.getCanCreateTool())
			.canUseTool(projectMember.getCanUseTool())
			.canUpdateTool(projectMember.getCanUpdateTool())
			.canDeleteTool(projectMember.getCanDeleteTool())
			.status(projectMember.getStatus())
			.createdByUserId(projectMember.getCreatedByUser() == null ? null : projectMember.getCreatedByUser().getId())
			.createdAt(projectMember.getCreatedAt())
			.updatedAt(projectMember.getUpdatedAt())
			.build();
	}
}
