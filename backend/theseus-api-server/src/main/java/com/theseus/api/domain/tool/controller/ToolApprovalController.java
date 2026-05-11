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
@Tag(name = "ToolApproval", description = "Tool 승인 관리 API")
@RequestMapping("/api/v1/projects/{projectId}")
public class ToolApprovalController {

	private final ToolApprovalService toolApprovalService;

	@Operation(
		summary = "Tool 승인 요청 목록 조회",
		description = "프로젝트 ADMIN 또는 MANAGER가 프로젝트의 Tool 승인 요청 목록을 조회합니다."
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
		summary = "Tool 승인 요청 상세 조회",
		description = "프로젝트 ADMIN 또는 MANAGER가 Tool 승인 요청 상세 정보를 조회합니다."
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
		summary = "Tool 승인 요청",
		description = "Tool 생성자가 REVIEW 단계의 Draft Tool에 대한 승인을 요청합니다."
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
		summary = "ToolPlan 승인 요청",
		description = "ToolPlan 생성자가 REVIEW 상태의 ToolPlan에 대한 승인을 요청합니다."
	)
	@PostMapping("/tool-plans/{toolPlanId}/approval-requests")
	public ResponseEntity<ApiResponse<ToolApprovalResponse>> requestToolPlanApproval(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long toolPlanId
	) {
		ToolApprovalResponse response = toolApprovalService.requestToolPlanApproval(currentUser, projectId, toolPlanId);
		return ApiResponse.onSuccess(SuccessCode.CREATED, response);
	}

	@Operation(
		summary = "Tool 승인",
		description = "프로젝트 ADMIN 또는 MANAGER가 대기 중인 Tool 승인 요청을 승인합니다."
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
		summary = "Tool 반려",
		description = "프로젝트 ADMIN 또는 MANAGER가 대기 중인 Tool 승인 요청을 반려합니다."
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
