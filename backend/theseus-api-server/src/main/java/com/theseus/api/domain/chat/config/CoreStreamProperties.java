package com.theseus.api.domain.chat.config;

import java.net.URI;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "theseus.core")
public record CoreStreamProperties(String baseUrl) {

	private static final String DEFAULT_BASE_URL = "http://localhost:8086";

	public CoreStreamProperties {
		if (baseUrl == null || baseUrl.isBlank()) {
			baseUrl = DEFAULT_BASE_URL;
		}
	}

	public URI streamUri(Long projectId, Long sessionId) {
		String normalizedBaseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
		String query = "chat_session_id=%d&project_id=%d".formatted(sessionId, projectId);
		return URI.create(normalizedBaseUrl + "/api/v1/stream?" + query);
	}
}
