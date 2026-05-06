package com.theseus.api.domain.toolgeneration.dto.request;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotEmpty;
import java.util.List;
import lombok.Getter;

@Getter
public class ToolRegenerationRequest {

	private Long baseDraftVersion;

	@Valid
	@NotEmpty
	private List<ToolFeedbackItemRequest> feedbackItems;
}
