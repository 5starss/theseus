package com.theseus.api.domain.auth.dto.request;

import jakarta.validation.constraints.NotBlank;
import lombok.Getter;

@Getter
public class InternalAuthVerifyRequest {

	@NotBlank
	private String token;

	private Long projectId;

	private Long chatSessionId;
}
