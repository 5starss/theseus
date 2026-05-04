package com.theseus.api.domain.project.controller;

import com.theseus.api.common.response.ApiResponse;
import com.theseus.api.common.response.status.SuccessCode;
import com.theseus.api.domain.project.dto.request.InternalProjectPermissionRequest;
import com.theseus.api.domain.project.service.InternalProjectPermissionService;
import jakarta.validation.Valid;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RequiredArgsConstructor
@RequestMapping("/api/internal/project")
@RestController
public class InternalProjectController {

	private final InternalProjectPermissionService internalProjectPermissionService;

	@PostMapping("/permissions")
	public ResponseEntity<ApiResponse<Map<String, Integer>>> getToolPermissions(
		@Valid @RequestBody InternalProjectPermissionRequest request
	) {
		Map<String, Integer> response = internalProjectPermissionService.getToolPermissions(request);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}
}
