package com.theseus.api.domain.toolgeneration.event;

import java.util.Locale;

public enum ToolBuildEventType {
	TOOL_BUILD_COMPLETED,
	TOOL_BUILD_FAILED,
	PROGRESS,
	CHUNK,
	UNKNOWN;

	public static ToolBuildEventType from(String eventType) {
		if (eventType == null || eventType.isBlank()) {
			return UNKNOWN;
		}

		String normalizedEventType = eventType.trim().toUpperCase(Locale.ROOT);
		return switch (normalizedEventType) {
			case "TOOL_BUILD_COMPLETED" -> TOOL_BUILD_COMPLETED;
			case "TOOL_BUILD_FAILED" -> TOOL_BUILD_FAILED;
			case "PROGRESS" -> PROGRESS;
			case "CHUNK" -> CHUNK;
			default -> UNKNOWN;
		};
	}
}
