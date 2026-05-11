package com.theseus.api.domain.toolgeneration.dto.response;

import com.theseus.api.domain.tool.entity.ToolPlanRun;
import com.theseus.api.domain.tool.entity.ToolPlanRunStatus;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ToolPlanGenerationRunResponse {

	private String runId;
	private Long projectId;
	private Long sessionId;
	private ToolPlanRunStatus status;
	private String sseUrl;

	public static ToolPlanGenerationRunResponse createFrom(ToolPlanRun toolPlanRun) {
		Long projectId = toolPlanRun.getProject().getId();
		Long sessionId = toolPlanRun.getChatSession().getId();
		String runId = toolPlanRun.getRunId();

		return ToolPlanGenerationRunResponse.builder()
			.runId(runId)
			.projectId(projectId)
			.sessionId(sessionId)
			.status(toolPlanRun.getStatus())
			.sseUrl(
				"/api/v1/projects/" + projectId
					+ "/sessions/" + sessionId
					+ "/tool-plan-runs/" + runId
					+ "/events"
			)
			.build();
	}
}
