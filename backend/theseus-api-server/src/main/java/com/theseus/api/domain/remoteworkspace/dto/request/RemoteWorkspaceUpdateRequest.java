package com.theseus.api.domain.remoteworkspace.dto.request;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import lombok.Getter;

@Getter
public class RemoteWorkspaceUpdateRequest {

	private String name;

	private String host;

	@Min(1)
	@Max(65535)
	private Integer port;

	private String username;

	private String password;

	private String privateKeyPath;

	private String basePath;

	private Boolean allowWriteExecution;
}
