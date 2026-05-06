package com.theseus.api.domain.tool.dto.response;

import com.fasterxml.jackson.databind.JsonNode;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolDraftPhase;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class InternalToolDraftResponse {

	private Long toolId;
	private Long projectId;
	private Long chatSessionId;
	private String rawMarkdown;
	private JsonNode structuredPlanJson;
	private JsonNode draftSnapshot;
	private ToolDraftPhase draftPhase;
	private Long draftVersion;

	public static InternalToolDraftResponse createOf(
		Tool tool,
		JsonNode structuredPlanJson,
		JsonNode draftSnapshot
	) {
		return InternalToolDraftResponse.builder()
			.toolId(tool.getId())
			.projectId(tool.getProject().getId())
			.chatSessionId(tool.getChatSession().getId())
			.rawMarkdown(tool.getRawMarkdown())
			.structuredPlanJson(structuredPlanJson)
			.draftSnapshot(draftSnapshot)
			.draftPhase(tool.getDraftPhase())
			.draftVersion(tool.getDraftVersion())
			.build();
	}
}
