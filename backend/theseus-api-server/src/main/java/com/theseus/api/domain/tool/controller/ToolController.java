package com.theseus.api.domain.tool.controller;

import com.theseus.api.common.response.ApiResponse;
import com.theseus.api.common.response.status.SuccessCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.tool.dto.response.ToolDetailResponse;
import com.theseus.api.domain.tool.dto.response.ToolPageResponse;
import com.theseus.api.domain.tool.dto.response.ToolSummaryResponse;
import com.theseus.api.domain.tool.entity.ToolStatus;
import com.theseus.api.domain.tool.service.ToolService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@Tag(name = "Tool", description = "Tool 관리 API")
@RequestMapping("/api/v1/projects/{projectId}/tools")
public class ToolController {

	private final ToolService toolService;

	@Operation(
		summary = "Tool 목록 조회",
		description = "프로젝트 멤버가 사용 권한과 접근 레벨 기준으로 접근 가능한 승인 Tool 목록을 조회합니다."
	)
	@GetMapping
	public ResponseEntity<ApiResponse<ToolPageResponse<ToolSummaryResponse>>> getTools(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@RequestParam(defaultValue = "accessible") String scope,
		@RequestParam(defaultValue = "APPROVED") ToolStatus status,
		@RequestParam(defaultValue = "0") int page,
		@RequestParam(defaultValue = "20") int size
	) {
		Page<ToolSummaryResponse> tools = toolService.getTools(currentUser, projectId, scope, status, page, size);
		return ApiResponse.onSuccess(SuccessCode.OK, ToolPageResponse.createFrom(tools));
	}

	@Operation(
		summary = "Tool 상세 조회",
		description = "프로젝트 멤버가 사용 권한과 접근 레벨 기준으로 접근 가능한 승인 Tool 상세 정보를 조회합니다."
	)
	@GetMapping("/{toolId}")
	public ResponseEntity<ApiResponse<ToolDetailResponse>> getTool(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long toolId
	) {
		ToolDetailResponse response = toolService.getTool(currentUser, projectId, toolId);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}
}
