package com.theseus.api.domain.remoteworkspace.dto.response;

import com.theseus.api.domain.remoteworkspace.entity.RemoteWorkspace;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class RemoteWorkspaceConnectionTestResponse {

	private Long remoteWorkspaceId;
	private Boolean available;
	private String message;

	public static RemoteWorkspaceConnectionTestResponse createPendingFrom(RemoteWorkspace remoteWorkspace) {
		return RemoteWorkspaceConnectionTestResponse.builder()
			.remoteWorkspaceId(remoteWorkspace.getId())
			.available(false)
			.message("SSH connection test will be supported after Core connector integration.")
			.build();
	}
}
