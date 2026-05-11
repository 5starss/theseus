package com.theseus.api.domain.tool.dto.request;

import jakarta.validation.constraints.Min;
import lombok.Getter;

@Getter
public class ToolApprovalApproveRequest {

	@Min(1)
	private Integer toolGrade;

	private String reviewFeedback;
}
