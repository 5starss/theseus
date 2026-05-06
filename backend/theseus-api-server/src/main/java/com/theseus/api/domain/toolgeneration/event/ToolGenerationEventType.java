package com.theseus.api.domain.toolgeneration.event;

import java.util.Locale;

public enum ToolGenerationEventType {
	TOOL_GENERATION_COMPLETED,
	TOOL_GENERATION_FAILED,
	PROGRESS,
	CHUNK,
	UNKNOWN;

	public static ToolGenerationEventType from(String eventType) {
		if (eventType == null || eventType.isBlank()) {
			return UNKNOWN;
		}

		String normalizedEventType = eventType.trim().toUpperCase(Locale.ROOT);
		return switch (normalizedEventType) {
			case "TOOL_GENERATION_COMPLETED", "COMPLETED" -> TOOL_GENERATION_COMPLETED;
			case "TOOL_GENERATION_FAILED", "FAILED" -> TOOL_GENERATION_FAILED;
			case "PROGRESS" -> PROGRESS;
			case "CHUNK" -> CHUNK;
			default -> UNKNOWN;
		};
	}

	public boolean isProgressEvent() {
		return this == PROGRESS || this == CHUNK;
	}
}
