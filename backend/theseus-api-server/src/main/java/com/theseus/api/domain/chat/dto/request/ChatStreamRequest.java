package com.theseus.api.domain.chat.dto.request;

import com.theseus.api.domain.tool.entity.ToolPlanMode;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;

@Getter
public class ChatStreamRequest {

	@NotNull
	private ToolPlanMode mode;

	@NotBlank
	private String prompt;

	private Long remoteWorkspaceId;
}
