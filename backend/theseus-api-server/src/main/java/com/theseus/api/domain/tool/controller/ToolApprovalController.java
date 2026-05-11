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

	@Operation(summary = "ToolApproval list", description = "Returns project ToolPlan approval requests.")
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

	@Operation(summary = "ToolApproval detail", description = "Returns a ToolPlan approval request.")
	@GetMapping("/tool-approvals/{toolApprovalId}")
	public ResponseEntity<ApiResponse<ToolApprovalResponse>> getToolApproval(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long toolApprovalId
	) {
		ToolApprovalResponse response = toolApprovalService.getToolApproval(currentUser, projectId, toolApprovalId);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}

	@Operation(summary = "ToolPlan approval request", description = "Requests approval for a REVIEW ToolPlan.")
	@PostMapping("/tool-plans/{toolPlanId}/approval-requests")
	public ResponseEntity<ApiResponse<ToolApprovalResponse>> requestToolPlanApproval(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long toolPlanId
	) {
		ToolApprovalResponse response = toolApprovalService.requestToolPlanApproval(currentUser, projectId, toolPlanId);
		return ApiResponse.onSuccess(SuccessCode.CREATED, response);
	}

	@Operation(summary = "ToolApproval approve", description = "Approves a pending ToolPlan approval request.")
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

	@Operation(summary = "ToolApproval reject", description = "Rejects a pending ToolPlan approval request.")
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
