package com.theseus.api.domain.toolgeneration.dto.response;

import com.theseus.api.domain.tool.entity.ToolPlan;
import com.theseus.api.domain.tool.entity.ToolPlanGroup;
import com.theseus.api.domain.tool.entity.ToolPlanGroupStatus;
import com.theseus.api.domain.tool.entity.ToolPlanRun;
import com.theseus.api.domain.tool.entity.ToolPlanRunRequestType;
import com.theseus.api.domain.tool.entity.ToolPlanRunStatus;
import com.theseus.api.domain.toolgeneration.dto.ToolPlanRunState;
import java.time.LocalDateTime;
import lombok.Builder;
import lombok.Getter;

@Getter
@Builder
public class ToolPlanRunStateResponse {

	private static final String EVENT_TYPE_STATE = "state";

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

	public static ToolPlanRunStateResponse createFrom(ToolPlanRunState state) {
		return ToolPlanRunStateResponse.builder()
			.runId(state.getRunId())
			.projectId(state.getProjectId())
			.chatSessionId(state.getChatSessionId())
			.toolPlanGroupId(state.getToolPlanGroupId())
			.toolPlanId(state.getToolPlanId())
			.planVersion(state.getPlanVersion())
			.eventType(state.getEventType())
			.status(state.getStatus())
			.progressRate(state.getProgressRate())
			.message(state.getMessage())
			.content(state.getContent())
			.errorCode(state.getErrorCode())
			.errorMessage(state.getErrorMessage())
			.updatedAt(state.getUpdatedAt())
			.build();
	}

	public static ToolPlanRunStateResponse createFallbackFrom(ToolPlanRun toolPlanRun) {
		ToolPlan toolPlan = resolveToolPlan(toolPlanRun);
		ToolPlanGroup planGroup = resolvePlanGroup(toolPlanRun, toolPlan);

		return ToolPlanRunStateResponse.builder()
			.runId(toolPlanRun.getRunId())
			.projectId(toolPlanRun.getProject().getId())
			.chatSessionId(toolPlanRun.getChatSession().getId())
			.toolPlanGroupId(planGroup == null ? null : planGroup.getId())
			.toolPlanId(toolPlan == null ? null : toolPlan.getId())
			.planVersion(toolPlan == null ? null : toolPlan.getPlanVersion())
			.eventType(EVENT_TYPE_STATE)
			.status(resolveFallbackStatus(toolPlanRun, planGroup, toolPlan))
			.errorCode(toolPlanRun.getErrorCode())
			.errorMessage(toolPlanRun.getErrorMessage())
			.updatedAt(toolPlanRun.getUpdatedAt())
			.build();
	}

	private static ToolPlan resolveToolPlan(ToolPlanRun toolPlanRun) {
		if (toolPlanRun.getResultToolPlan() != null) {
			return toolPlanRun.getResultToolPlan();
		}
		return toolPlanRun.getBaseToolPlan();
	}

	private static ToolPlanGroup resolvePlanGroup(ToolPlanRun toolPlanRun, ToolPlan toolPlan) {
		if (toolPlanRun.getPlanGroup() != null) {
			return toolPlanRun.getPlanGroup();
		}
		if (toolPlan != null) {
			return toolPlan.getPlanGroup();
		}
		return null;
	}

	private static String resolveFallbackStatus(ToolPlanRun toolPlanRun, ToolPlanGroup planGroup, ToolPlan toolPlan) {
		if (ToolPlanRunStatus.COMPLETED.equals(toolPlanRun.getStatus())) {
			if (ToolPlanRunRequestType.BUILD_TOOL.equals(toolPlanRun.getRequestType())
				&& planGroup != null
				&& ToolPlanGroupStatus.BUILT.equals(planGroup.getStatus())) {
				return ToolPlanGroupStatus.BUILT.name();
			}
			if (toolPlan != null) {
				return toolPlan.getStatus().name();
			}
		}
		return toolPlanRun.getStatus().name();
	}
}
