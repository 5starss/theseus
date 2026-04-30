package com.theseus.api.domain.tool.controller;

import com.theseus.api.common.response.ApiResponse;
import com.theseus.api.common.response.status.SuccessCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.tool.dto.request.ToolApprovalApproveRequest;
import com.theseus.api.domain.tool.dto.request.ToolApprovalRejectRequest;
import com.theseus.api.domain.tool.dto.response.ToolApprovalPageResponse;
import com.theseus.api.domain.tool.dto.response.ToolApprovalResponse;
import com.theseus.api.domain.tool.entity.ToolApprovalStatus;
import com.theseus.api.domain.tool.service.ToolApprovalService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@Tag(name = "ToolApproval", description = "Tool approval API")
@RequestMapping("/api/v1/projects/{projectId}")
public class ToolApprovalController {

	private final ToolApprovalService toolApprovalService;

	@Operation(
		summary = "Get Tool approval requests",
		description = "Project ADMIN or MANAGER retrieves Tool approval requests in the project."
	)
	@GetMapping("/tool-approvals")
	public ResponseEntity<ApiResponse<ToolApprovalPageResponse<ToolApprovalResponse>>> getToolApprovals(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@RequestParam(required = false) ToolApprovalStatus approvalStatus,
		@RequestParam(defaultValue = "0") int page,
		@RequestParam(defaultValue = "20") int size
	) {
		Page<ToolApprovalResponse> toolApprovals = toolApprovalService.getToolApprovals(
			currentUser,
			projectId,
			approvalStatus,
			page,
			size
		);
		return ApiResponse.onSuccess(SuccessCode.OK, ToolApprovalPageResponse.createFrom(toolApprovals));
	}

	@Operation(
		summary = "Get Tool approval request detail",
		description = "Project ADMIN or MANAGER retrieves a Tool approval request detail."
	)
	@GetMapping("/tool-approvals/{toolApprovalId}")
	public ResponseEntity<ApiResponse<ToolApprovalResponse>> getToolApproval(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long toolApprovalId
	) {
		ToolApprovalResponse response = toolApprovalService.getToolApproval(currentUser, projectId, toolApprovalId);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}

	@Operation(
		summary = "Request Tool approval",
		description = "The Tool creator requests approval for a Draft Tool in REVIEW phase."
	)
	@PostMapping("/tools/{toolId}/approval-requests")
	public ResponseEntity<ApiResponse<ToolApprovalResponse>> requestToolApproval(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long toolId
	) {
		ToolApprovalResponse response = toolApprovalService.requestToolApproval(currentUser, projectId, toolId);
		return ApiResponse.onSuccess(SuccessCode.CREATED, response);
	}

	@Operation(
		summary = "Approve Tool approval request",
		description = "Project ADMIN or MANAGER approves a pending Tool approval request."
	)
	@PatchMapping("/tool-approvals/{toolApprovalId}/approve")
	public ResponseEntity<ApiResponse<ToolApprovalResponse>> approveToolApproval(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long toolApprovalId,
		@Valid @RequestBody ToolApprovalApproveRequest request
	) {
		ToolApprovalResponse response = toolApprovalService.approveToolApproval(
			currentUser,
			projectId,
			toolApprovalId,
			request
		);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}

	@Operation(
		summary = "Reject Tool approval request",
		description = "Project ADMIN or MANAGER rejects a pending Tool approval request."
	)
	@PatchMapping("/tool-approvals/{toolApprovalId}/reject")
	public ResponseEntity<ApiResponse<ToolApprovalResponse>> rejectToolApproval(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long toolApprovalId,
		@Valid @RequestBody ToolApprovalRejectRequest request
	) {
		ToolApprovalResponse response = toolApprovalService.rejectToolApproval(
			currentUser,
			projectId,
			toolApprovalId,
			request
		);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}
}
