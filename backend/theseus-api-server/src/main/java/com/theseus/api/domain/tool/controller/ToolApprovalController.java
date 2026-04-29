package com.theseus.api.domain.tool.controller;

import com.theseus.api.common.response.ApiResponse;
import com.theseus.api.common.response.status.SuccessCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.tool.dto.response.ToolApprovalResponse;
import com.theseus.api.domain.tool.service.ToolApprovalService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@Tag(name = "ToolApproval", description = "Tool approval API")
@RequestMapping("/api/v1/projects/{projectId}/tools/{toolId}/approval-requests")
public class ToolApprovalController {

	private final ToolApprovalService toolApprovalService;

	@Operation(
		summary = "Request Tool approval",
		description = "The Tool creator requests approval for a Draft Tool in REVIEW phase."
	)
	@PostMapping
	public ResponseEntity<ApiResponse<ToolApprovalResponse>> requestToolApproval(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long toolId
	) {
		ToolApprovalResponse response = toolApprovalService.requestToolApproval(currentUser, projectId, toolId);
		return ApiResponse.onSuccess(SuccessCode.CREATED, response);
	}
}
