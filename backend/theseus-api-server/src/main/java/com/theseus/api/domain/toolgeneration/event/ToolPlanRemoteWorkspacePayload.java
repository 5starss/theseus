package com.theseus.api.domain.toolgeneration.event;

import com.theseus.api.domain.remoteworkspace.entity.RemoteWorkspace;

public record ToolPlanRemoteWorkspacePayload(
	Long id,
	Long remoteWorkspaceId,
	Long projectId,
	Long createdByProjectMemberId,
	String name,
	String host,
	Integer port,
	String username,
	String password,
	String privateKeyPath,
	String basePath,
	String status
) {

	public static ToolPlanRemoteWorkspacePayload createFrom(RemoteWorkspace remoteWorkspace) {
		if (remoteWorkspace == null) {
			return null;
		}

		return new ToolPlanRemoteWorkspacePayload(
			remoteWorkspace.getId(),
			remoteWorkspace.getId(),
			remoteWorkspace.getProject().getId(),
			remoteWorkspace.getCreatedByProjectMember().getId(),
			remoteWorkspace.getName(),
			remoteWorkspace.getHost(),
			remoteWorkspace.getPort(),
			remoteWorkspace.getUsername(),
			remoteWorkspace.getPassword(),
			remoteWorkspace.getPrivateKeyPath(),
			remoteWorkspace.getBasePath(),
			remoteWorkspace.getStatus().name()
		);
	}
}
