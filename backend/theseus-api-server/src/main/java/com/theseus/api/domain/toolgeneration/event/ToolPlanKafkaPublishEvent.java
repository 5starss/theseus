package com.theseus.api.domain.toolgeneration.event;

public record ToolPlanKafkaPublishEvent(
	String key,
	Object payload
) {
}
