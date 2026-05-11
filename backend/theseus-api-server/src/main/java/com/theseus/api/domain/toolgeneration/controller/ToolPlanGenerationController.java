package com.theseus.api.domain.toolgeneration.controller;

import com.theseus.api.common.response.ApiResponse;
import com.theseus.api.common.response.status.SuccessCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.toolgeneration.dto.request.ToolPlanGenerationRequest;
import com.theseus.api.domain.toolgeneration.dto.request.ToolPlanRegenerationRequest;
import com.theseus.api.domain.toolgeneration.dto.response.ToolPlanGenerationRunResponse;
import com.theseus.api.domain.toolgeneration.service.ToolPlanGenerationService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@Tag(name = "ToolPlan", description = "Tool PLAN 생성 API")
@RequestMapping("/api/v1/projects/{projectId}/sessions/{sessionId}/tool-plans")
public class ToolPlanGenerationController {

	private final ToolPlanGenerationService toolPlanGenerationService;

	@Operation(
		summary = "PLAN 생성 요청",
		description = "Tool이나 ToolPlan을 즉시 만들지 않고 ToolPlanRun을 기록한 뒤 Kafka에 PLAN 생성 요청을 발행합니다."
	)
	@PostMapping("/generate")
	public ResponseEntity<ApiResponse<ToolPlanGenerationRunResponse>> generatePlan(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long sessionId,
		@Valid @RequestBody ToolPlanGenerationRequest request
	) {
		ToolPlanGenerationRunResponse response = toolPlanGenerationService.generatePlan(
			currentUser,
			projectId,
			sessionId,
			request
		);
		return ApiResponse.onSuccess(SuccessCode.ACCEPTED, response);
	}

	@Operation(
		summary = "PLAN 재생성 요청",
		description = "기존 ToolPlan을 기준으로 사용자 피드백을 저장하고 ToolPlanRun 재생성 요청을 Kafka에 발행합니다."
	)
	@PatchMapping("/{toolPlanId}/regenerate")
	public ResponseEntity<ApiResponse<ToolPlanGenerationRunResponse>> regeneratePlan(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long sessionId,
		@PathVariable Long toolPlanId,
		@Valid @RequestBody ToolPlanRegenerationRequest request
	) {
		ToolPlanGenerationRunResponse response = toolPlanGenerationService.regeneratePlan(
			currentUser,
			projectId,
			sessionId,
			toolPlanId,
			request
		);
		return ApiResponse.onSuccess(SuccessCode.ACCEPTED, response);
	}
}
