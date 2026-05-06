package com.theseus.api.domain.toolgeneration.dto.response;

import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolDraftPhase;
import com.theseus.api.domain.tool.entity.ToolStatus;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ToolGenerationRunResponse {

	private String runId;
	private Long toolId;
	private Long projectId;
	private Long sessionId;
	private ToolStatus status;
	private ToolDraftPhase draftPhase;
	private Long draftVersion;
	private String sseUrl;

	public static ToolGenerationRunResponse createOf(String runId, Tool tool) {
		return ToolGenerationRunResponse.builder()
			.runId(runId)
			.toolId(tool.getId())
			.projectId(tool.getProject().getId())
			.sessionId(tool.getChatSession().getId())
			.status(tool.getStatus())
			.draftPhase(tool.getDraftPhase())
			.draftVersion(tool.getDraftVersion())
			.sseUrl("/api/v1/tool-runs/" + runId + "/events")
			.build();
	}
}
