package com.theseus.api.domain.chat.dto.request;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Getter;

@Getter
public class ChatSessionUpdateRequest {

	@NotBlank
	@Size(max = 150)
	private String title;
}
