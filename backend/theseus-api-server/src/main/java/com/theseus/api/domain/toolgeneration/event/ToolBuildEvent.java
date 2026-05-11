package com.theseus.api.domain.toolgeneration.event;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class ToolBuildEvent {

	private String eventType;
	private String runId;
	private Long eventSequence;
	private Long projectId;
	private Long chatSessionId;
	private Long toolPlanId;
	private ToolBuildArtifactPayload artifact;
	private Integer progressRate;
	private String code;
	private String message;
	private String content;
	private String completedAt;
	private String failedAt;

	public ToolBuildEventType getEventTypeValue() {
		return ToolBuildEventType.from(eventType);
	}
}
