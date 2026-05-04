package com.theseus.api.domain.auth.controller;

import com.theseus.api.common.response.ApiResponse;
import com.theseus.api.common.response.status.SuccessCode;
import com.theseus.api.domain.auth.dto.request.InternalAuthVerifyRequest;
import com.theseus.api.domain.auth.dto.response.InternalAuthVerifyResponse;
import com.theseus.api.domain.auth.service.InternalAuthService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RequiredArgsConstructor
@RequestMapping("/api/internal/auth")
@RestController
public class InternalAuthController {

	private final InternalAuthService internalAuthService;

	@PostMapping("/verify")
	public ResponseEntity<ApiResponse<InternalAuthVerifyResponse>> verify(
		@Valid @RequestBody InternalAuthVerifyRequest request
	) {
		InternalAuthVerifyResponse response = internalAuthService.verify(request);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}
}
