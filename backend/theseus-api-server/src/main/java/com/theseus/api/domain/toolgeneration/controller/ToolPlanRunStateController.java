package com.theseus.api.domain.toolgeneration.controller;

import com.theseus.api.common.response.ApiResponse;
import com.theseus.api.common.response.status.SuccessCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.toolgeneration.dto.response.ToolPlanRunStateResponse;
import com.theseus.api.domain.toolgeneration.service.ToolPlanRunStateService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@Tag(name = "ToolPlanRun", description = "ToolPlanRun 진행 상태 API")
@RequestMapping("/api/v1/projects/{projectId}/sessions/{sessionId}/tool-plan-runs/{runId}")
public class ToolPlanRunStateController {

	private final ToolPlanRunStateService toolPlanRunStateService;

	@Operation(
		summary = "ToolPlanRun 진행 상태 조회",
		description = "Redis 최신 상태를 우선 조회하고 없으면 DB ToolPlanRun 상태로 진행 상태를 복구합니다."
	)
	@GetMapping("/state")
	public ResponseEntity<ApiResponse<ToolPlanRunStateResponse>> getToolPlanRunState(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long sessionId,
		@PathVariable String runId
	) {
		ToolPlanRunStateResponse response = toolPlanRunStateService.getToolPlanRunState(
			currentUser,
			projectId,
			sessionId,
			runId
		);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}
}
