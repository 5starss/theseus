package com.theseus.api.domain.remoteworkspace.dto.request;

import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor
public class RemoteWorkspaceConnectionConfigRequest {

	@NotNull
	private Long projectId;

	@NotNull
	private Long remoteWorkspaceId;
}
