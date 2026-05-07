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
public class ToolGenerationEvent {

	private String eventType;
	private String runId;
	private Long projectId;
	private Long chatSessionId;
	private Long toolId;
	private ToolGenerationAssistantMessagePayload assistantMessage;
	private ToolGenerationDraftPayload toolDraft;
	private Integer progressRate;
	private String code;
	private String message;
	private String content;
	private String completedAt;
	private String failedAt;

	public ToolGenerationEventType getEventTypeValue() {
		return ToolGenerationEventType.from(eventType);
	}
}
