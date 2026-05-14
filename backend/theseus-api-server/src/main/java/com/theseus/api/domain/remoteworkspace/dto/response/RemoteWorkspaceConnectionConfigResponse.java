package com.theseus.api.domain.remoteworkspace.dto.response;

import com.theseus.api.domain.remoteworkspace.entity.RemoteWorkspace;
import com.theseus.api.domain.remoteworkspace.entity.RemoteWorkspaceStatus;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class RemoteWorkspaceConnectionConfigResponse {

	private Long remoteWorkspaceId;
	private Long projectId;
	private String name;
	private String host;
	private Integer port;
	private String username;
	private String password;
	private String privateKeyPath;
	private String basePath;
	private Boolean allowWriteExecution;
	private RemoteWorkspaceStatus status;

	public static RemoteWorkspaceConnectionConfigResponse createFrom(RemoteWorkspace remoteWorkspace) {
		return RemoteWorkspaceConnectionConfigResponse.builder()
			.remoteWorkspaceId(remoteWorkspace.getId())
			.projectId(remoteWorkspace.getProject().getId())
			.name(remoteWorkspace.getName())
			.host(remoteWorkspace.getHost())
			.port(remoteWorkspace.getPort())
			.username(remoteWorkspace.getUsername())
			.password(remoteWorkspace.getPassword())
			.privateKeyPath(remoteWorkspace.getPrivateKeyPath())
			.basePath(remoteWorkspace.getBasePath())
			.allowWriteExecution(remoteWorkspace.isAllowWriteExecution())
			.status(remoteWorkspace.getStatus())
			.build();
	}
}
