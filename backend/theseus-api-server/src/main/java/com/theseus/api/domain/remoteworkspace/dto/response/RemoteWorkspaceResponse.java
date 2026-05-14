package com.theseus.api.domain.remoteworkspace.dto.response;

import com.theseus.api.domain.remoteworkspace.entity.RemoteWorkspace;
import com.theseus.api.domain.remoteworkspace.entity.RemoteWorkspaceStatus;
import java.time.LocalDateTime;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class RemoteWorkspaceResponse {

	private Long remoteWorkspaceId;
	private Long projectId;
	private Long createdByProjectMemberId;
	private String name;
	private String host;
	private Integer port;
	private String username;
	private String privateKeyPath;
	private String basePath;
	private Boolean allowWriteExecution;
	private RemoteWorkspaceStatus status;
	private LocalDateTime createdAt;
	private LocalDateTime updatedAt;

	public static RemoteWorkspaceResponse createFrom(RemoteWorkspace remoteWorkspace) {
		return RemoteWorkspaceResponse.builder()
			.remoteWorkspaceId(remoteWorkspace.getId())
			.projectId(remoteWorkspace.getProject().getId())
			.createdByProjectMemberId(remoteWorkspace.getCreatedByProjectMember().getId())
			.name(remoteWorkspace.getName())
			.host(remoteWorkspace.getHost())
			.port(remoteWorkspace.getPort())
			.username(remoteWorkspace.getUsername())
			.privateKeyPath(remoteWorkspace.getPrivateKeyPath())
			.basePath(remoteWorkspace.getBasePath())
			.allowWriteExecution(remoteWorkspace.isAllowWriteExecution())
			.status(remoteWorkspace.getStatus())
			.createdAt(remoteWorkspace.getCreatedAt())
			.updatedAt(remoteWorkspace.getUpdatedAt())
			.build();
	}
}
