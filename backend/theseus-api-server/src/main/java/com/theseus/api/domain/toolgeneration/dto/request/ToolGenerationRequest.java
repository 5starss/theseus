package com.theseus.api.domain.toolgeneration.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.Getter;

@Getter
public class ToolGenerationRequest {

	@NotBlank
	private String userMessage;

	@NotBlank
	private String fileName;
}
