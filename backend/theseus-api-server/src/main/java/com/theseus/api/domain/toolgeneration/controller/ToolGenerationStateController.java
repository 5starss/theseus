package com.theseus.api.domain.toolgeneration.controller;

import com.theseus.api.common.response.ApiResponse;
import com.theseus.api.common.response.status.SuccessCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.toolgeneration.dto.response.ToolGenerationStateResponse;
import com.theseus.api.domain.toolgeneration.service.ToolGenerationStateService;
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
@Tag(name = "ToolGeneration", description = "Tool 생성 진행 상태 API")
@RequestMapping("/api/v1/projects/{projectId}/sessions/{sessionId}/tools/{toolId}")
public class ToolGenerationStateController {

	private final ToolGenerationStateService toolGenerationStateService;

	@Operation(
		summary = "Tool 생성 상태 조회",
		description = "Redis 최신 상태를 우선 조회하고, 없으면 DB Tool 상태를 기반으로 Tool 생성 상태를 조회합니다."
	)
	@GetMapping("/generation-state")
	public ResponseEntity<ApiResponse<ToolGenerationStateResponse>> getToolGenerationState(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long sessionId,
		@PathVariable Long toolId
	) {
		ToolGenerationStateResponse response = toolGenerationStateService.getToolGenerationState(
			currentUser,
			projectId,
			sessionId,
			toolId
		);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}
}
