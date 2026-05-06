package com.theseus.api.domain.tool.controller;

import com.theseus.api.common.response.ApiResponse;
import com.theseus.api.common.response.status.SuccessCode;
import com.theseus.api.domain.tool.dto.response.InternalToolDraftResponse;
import com.theseus.api.domain.tool.service.InternalToolDraftService;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RequiredArgsConstructor
@RequestMapping("/api/internal/tools")
@RestController
public class InternalToolController {

	private final InternalToolDraftService internalToolDraftService;

	@GetMapping("/{toolId}/draft")
	public ResponseEntity<ApiResponse<InternalToolDraftResponse>> getToolDraft(
		@PathVariable Long toolId
	) {
		InternalToolDraftResponse response = internalToolDraftService.getToolDraft(toolId);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}
}
