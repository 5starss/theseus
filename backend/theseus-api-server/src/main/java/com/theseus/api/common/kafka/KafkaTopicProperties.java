package com.theseus.api.common.kafka;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "theseus.kafka.topics")
public record KafkaTopicProperties(
	String toolPlanRequest,
	String toolPlanEvent,
	String toolBuildRequest,
	String toolBuildEvent
) {
}
