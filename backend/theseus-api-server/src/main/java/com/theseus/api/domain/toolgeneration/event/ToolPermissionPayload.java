package com.theseus.api.domain.toolgeneration.event;

public record ToolPermissionPayload(
	Boolean canCreateTool,
	Boolean canUseTool,
	Boolean canUpdateTool,
	Boolean canDeleteTool
) {
}
