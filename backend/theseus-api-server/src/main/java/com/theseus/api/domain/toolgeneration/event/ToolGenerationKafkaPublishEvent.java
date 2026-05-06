package com.theseus.api.domain.toolgeneration.event;

public record ToolGenerationKafkaPublishEvent(
	String key,
	Object payload,
	boolean regeneration
) {
}
