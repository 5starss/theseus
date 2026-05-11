package com.theseus.api.domain.toolgeneration.event;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import com.fasterxml.jackson.databind.JsonNode;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class ToolBuildArtifactPayload {

	private String fileName;
	private String moduleName;
	private String artifactPath;
	private String codeSnapshot;
	private JsonNode metadataJson;
	private String displayName;
	private String displayDescription;
	private Integer permissionLevel;
}
