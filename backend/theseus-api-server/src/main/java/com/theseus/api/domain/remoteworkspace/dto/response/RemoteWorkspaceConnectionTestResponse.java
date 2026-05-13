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

	public static RemoteWorkspaceConnectionTestResponse createFrom(
		RemoteWorkspace remoteWorkspace,
		Boolean available,
		String message
	) {
		return RemoteWorkspaceConnectionTestResponse.builder()
			.remoteWorkspaceId(remoteWorkspace.getId())
			.available(available)
			.message(message)
			.build();
	}
}
