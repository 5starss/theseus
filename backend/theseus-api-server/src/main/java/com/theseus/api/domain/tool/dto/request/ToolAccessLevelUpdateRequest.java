package com.theseus.api.domain.tool.dto.request;

import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;

@Getter
public class ToolAccessLevelUpdateRequest {

	@NotNull
	@Min(1)
	@Max(5)
	private Integer accessLevel;
}
