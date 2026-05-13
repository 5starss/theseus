package com.theseus.api.domain.remoteworkspace.dto.request;

import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.remoteworkspace.entity.RemoteWorkspace;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;

@Getter
public class RemoteWorkspaceCreateRequest {

	@NotBlank
	private String name;

	@NotBlank
	private String host;

	@NotNull
	@Min(1)
	@Max(65535)
	private Integer port;

	@NotBlank
	private String username;

	private String password;

	private String privateKeyPath;

	@NotBlank
	private String basePath;

	public RemoteWorkspace toEntity(Project project, ProjectMember createdByProjectMember) {
		return RemoteWorkspace.builder()
			.project(project)
			.createdByProjectMember(createdByProjectMember)
			.name(name)
			.host(host)
			.port(port)
			.username(username)
			.password(password)
			.privateKeyPath(privateKeyPath)
			.basePath(basePath)
			.build();
	}
}
