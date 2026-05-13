package com.theseus.api.domain.toolgeneration.dto.request;

import com.theseus.api.domain.tool.entity.ToolPlanMode;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import java.util.List;
import lombok.Getter;

@Getter
public class ToolPlanRegenerationRequest {

	@NotNull
	private ToolPlanMode mode;

	@NotNull
	@Min(1)
	private Long basePlanVersion;

	@Valid
	@NotEmpty
	private List<ToolFeedbackItemRequest> feedbackItems;

	private Long remoteWorkspaceId;
}
