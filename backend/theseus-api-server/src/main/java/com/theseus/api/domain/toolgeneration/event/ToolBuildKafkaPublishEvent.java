package com.theseus.api.domain.toolgeneration.event;

public record ToolBuildKafkaPublishEvent(
	String key,
	Object payload
) {
}
