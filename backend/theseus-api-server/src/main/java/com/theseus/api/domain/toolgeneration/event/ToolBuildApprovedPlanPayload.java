package com.theseus.api.domain.toolgeneration.event;

import com.fasterxml.jackson.databind.JsonNode;

public record ToolBuildApprovedPlanPayload(
	String rawMarkdown,
	JsonNode structuredPlanJson,
	JsonNode planSnapshot
) {
}
