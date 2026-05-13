package com.theseus.api.domain.chat.config;

import com.theseus.api.domain.tool.entity.ToolPlanMode;
import java.net.URI;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "theseus.core")
public record CoreStreamProperties(String baseUrl) {

	private static final String DEFAULT_BASE_URL = "http://localhost:8086";

	public CoreStreamProperties {
		if (baseUrl == null || baseUrl.isBlank()) {
			baseUrl = DEFAULT_BASE_URL;
		}
	}

	public URI streamUri(String prompt, Long projectId, Long sessionId, ToolPlanMode mode, Long remoteWorkspaceId) {
		String normalizedBaseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
		String query = "prompt=%s&chat_session_id=%d&project_id=%d&mode=%s".formatted(
			encode(prompt),
			sessionId,
			projectId,
			mode.name()
		);
		if (remoteWorkspaceId != null) {
			query += "&remote_workspace_id=%d".formatted(remoteWorkspaceId);
		}
		return URI.create(normalizedBaseUrl + "/api/v1/stream?" + query);
	}

	public URI streamUri(Long projectId, Long sessionId) {
		String normalizedBaseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
		String query = "chat_session_id=%d&project_id=%d".formatted(sessionId, projectId);
		return URI.create(normalizedBaseUrl + "/api/v1/stream?" + query);
	}

	public URI remoteWorkspaceConnectionTestUri() {
		String normalizedBaseUrl = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
		return URI.create(normalizedBaseUrl + "/api/v1/remote-workspaces/test-connection");
	}

	private String encode(String value) {
		return URLEncoder.encode(value, StandardCharsets.UTF_8);
	}
}
