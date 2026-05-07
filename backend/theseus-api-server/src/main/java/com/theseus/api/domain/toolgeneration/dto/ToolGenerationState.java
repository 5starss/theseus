package com.theseus.api.domain.toolgeneration.dto;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
import java.time.LocalDateTime;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@Builder(toBuilder = true)
@NoArgsConstructor
@AllArgsConstructor
@JsonIgnoreProperties(ignoreUnknown = true)
public class ToolGenerationState {

	private Long projectId;
	private Long chatSessionId;
	private Long toolId;
	private String eventType;
	private String status;
	private String draftPhase;
	private Integer progressRate;
	private String message;
	private String content;
	private Integer draftVersion;
	private String errorCode;
	private String errorMessage;
	private LocalDateTime updatedAt;
}
