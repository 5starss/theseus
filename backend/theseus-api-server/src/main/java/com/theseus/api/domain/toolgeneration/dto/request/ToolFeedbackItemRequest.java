package com.theseus.api.domain.toolgeneration.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.Getter;

@Getter
public class ToolFeedbackItemRequest {

	@NotBlank
	private String blockId;

	@NotBlank
	private String comment;
}
