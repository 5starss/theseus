package com.theseus.api.domain.project.dto.request;

import jakarta.validation.constraints.NotNull;
import lombok.Getter;

@Getter
public class InternalProjectPermissionRequest {

	@NotNull
	private Long projectId;

	@NotNull
	private Long userId;
}
