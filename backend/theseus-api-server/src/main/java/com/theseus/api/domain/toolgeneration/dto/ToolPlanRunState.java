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
public class ToolPlanRunState {

	private String runId;
	private Long projectId;
	private Long chatSessionId;
	private Long toolPlanGroupId;
	private Long toolPlanId;
	private Long planVersion;
	private String eventType;
	private String status;
	private Integer progressRate;
	private String message;
	private String content;
	private String errorCode;
	private String errorMessage;
	private LocalDateTime updatedAt;
}
