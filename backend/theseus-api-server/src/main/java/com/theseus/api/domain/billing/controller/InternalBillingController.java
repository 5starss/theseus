package com.theseus.api.domain.billing.controller;

import com.theseus.api.common.response.ApiResponse;
import com.theseus.api.common.response.status.SuccessCode;
import com.theseus.api.domain.billing.dto.request.BillingUsageCreateRequest;
import com.theseus.api.domain.billing.dto.response.BillingUsageResponse;
import com.theseus.api.domain.billing.service.BillingUsageService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RequiredArgsConstructor
@RequestMapping("/api/internal/billing")
@RestController
public class InternalBillingController {

	private static final String IDEMPOTENCY_KEY_HEADER = "X-Idempotency-Key";

	private final BillingUsageService billingUsageService;

	@PostMapping("/usage")
	public ResponseEntity<ApiResponse<BillingUsageResponse>> createUsage(
		@RequestHeader(value = IDEMPOTENCY_KEY_HEADER, required = false) String idempotencyKey,
		@Valid @RequestBody BillingUsageCreateRequest request
	) {
		BillingUsageResponse response = billingUsageService.createUsage(request, idempotencyKey);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}
}
