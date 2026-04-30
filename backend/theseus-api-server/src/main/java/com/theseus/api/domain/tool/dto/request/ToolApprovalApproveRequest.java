package com.theseus.api.domain.tool.dto.request;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;

@Getter
public class ToolApprovalApproveRequest {

	@NotNull
	@Min(1)
	private Integer toolGrade;

	private String reviewFeedback;
}
