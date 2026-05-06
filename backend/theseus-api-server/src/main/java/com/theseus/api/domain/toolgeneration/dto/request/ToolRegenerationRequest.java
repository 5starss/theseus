package com.theseus.api.domain.toolgeneration.dto.request;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import java.util.List;
import lombok.Getter;

@Getter
public class ToolRegenerationRequest {

	@NotNull
	private Long baseDraftVersion;

	@Valid
	@NotEmpty
	private List<ToolFeedbackItemRequest> feedbackItems;
}
