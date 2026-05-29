package com.theseus.api.domain.tool.controller;

import com.theseus.api.common.response.ApiResponse;
import com.theseus.api.common.response.status.SuccessCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.tool.dto.response.ToolUsageListResponse;
import com.theseus.api.domain.tool.entity.ToolUsageStatus;
import com.theseus.api.domain.tool.service.ToolUsageService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@Tag(name = "ToolUsage", description = "Tool usage history API")
@RequestMapping("/api/v1/projects/{projectId}/admin/tool-usages")
public class ToolUsageController {

	private final ToolUsageService toolUsageService;

	@Operation(summary = "Tool usage history", description = "Returns project Tool calling history for project admins.")
	@GetMapping
	public ResponseEntity<ApiResponse<ToolUsageListResponse>> getToolUsages(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@RequestParam(defaultValue = "0") int page,
		@RequestParam(defaultValue = "20") int size,
		@RequestParam(required = false) ToolUsageStatus status
	) {
		ToolUsageListResponse response = toolUsageService.getToolUsages(
			currentUser,
			projectId,
			page,
			size,
			status
		);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}
}
