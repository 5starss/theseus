package com.theseus.api.domain.toolgeneration.config;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "theseus.tool-generation")
public record ToolGenerationStateProperties(
	long stateTtlMinutes,
	long sseTimeoutMillis
) {

	public Duration stateTtl() {
		return Duration.ofMinutes(stateTtlMinutes);
	}

	public long sseTimeoutMillis() {
		return sseTimeoutMillis;
	}
}
