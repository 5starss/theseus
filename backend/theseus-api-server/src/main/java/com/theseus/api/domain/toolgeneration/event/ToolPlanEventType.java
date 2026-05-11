package com.theseus.api.domain.toolgeneration.event;

import java.util.Locale;

public enum ToolPlanEventType {
	TOOL_PLAN_COMPLETED,
	TOOL_PLAN_SKIPPED,
	TOOL_PLAN_FAILED,
	PROGRESS,
	CHUNK,
	UNKNOWN;

	public static ToolPlanEventType from(String eventType) {
		if (eventType == null || eventType.isBlank()) {
			return UNKNOWN;
		}

		String normalizedEventType = eventType.trim().toUpperCase(Locale.ROOT);
		return switch (normalizedEventType) {
			case "TOOL_PLAN_COMPLETED" -> TOOL_PLAN_COMPLETED;
			case "TOOL_PLAN_SKIPPED" -> TOOL_PLAN_SKIPPED;
			case "TOOL_PLAN_FAILED" -> TOOL_PLAN_FAILED;
			case "PROGRESS" -> PROGRESS;
			case "CHUNK" -> CHUNK;
			default -> UNKNOWN;
		};
	}
}
