package com.theseus.api.domain.billing.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.billing.dto.request.BillingUsageCreateRequest;
import com.theseus.api.domain.billing.dto.request.BillingUsageMetricsRequest;
import com.theseus.api.domain.billing.dto.response.BillingUsageResponse;
import com.theseus.api.domain.billing.entity.BillingUsage;
import com.theseus.api.domain.billing.repository.BillingUsageRepository;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

@RequiredArgsConstructor
@Service
public class BillingUsageService {

	private static final String DEFAULT_MODEL_NAME = "unknown";

	private final BillingUsageRepository billingUsageRepository;
	private final UserRepository userRepository;
	private final ProjectRepository projectRepository;
	private final ObjectMapper objectMapper;

	@Transactional
	public BillingUsageResponse createUsage(BillingUsageCreateRequest request, String idempotencyKey) {
		validateRequest(request);
		String normalizedIdempotencyKey = normalizeIdempotencyKey(idempotencyKey);
		if (normalizedIdempotencyKey != null) {
			return billingUsageRepository.findByIdempotencyKey(normalizedIdempotencyKey)
				.map(BillingUsageResponse::createFrom)
				.orElseGet(() -> createNewUsage(request, normalizedIdempotencyKey));
		}

		return createNewUsage(request, null);
	}

	private BillingUsageResponse createNewUsage(BillingUsageCreateRequest request, String idempotencyKey) {
		BillingUsageMetricsRequest usage = request.getUsage();
		User user = userRepository.findById(request.getUserId())
			.orElseThrow(() -> BusinessException.of(ErrorCode.USER_NOT_FOUND));
		Project project = projectRepository.findById(request.getProjectId())
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_NOT_FOUND));

		BillingUsage billingUsage = BillingUsage.builder()
			.user(user)
			.project(project)
			.promptTokens(normalizeToken(usage.getPromptTokens()))
			.completionTokens(normalizeToken(usage.getCompletionTokens()))
			.totalTokens(normalizeToken(usage.getTotalTokens()))
			.modelName(normalizeModelName(usage.getModelName()))
			.reportedAt(parseReportedAt(request.getTimestamp()))
			.idempotencyKey(idempotencyKey)
			.usagePayloadJson(convertUsagePayloadJson(usage))
			.build();

		return BillingUsageResponse.createFrom(billingUsageRepository.save(billingUsage));
	}

	private void validateRequest(BillingUsageCreateRequest request) {
		if (request == null || request.getUserId() == null || request.getProjectId() == null || request.getUsage() == null) {
			throw BusinessException.of(ErrorCode.BILLING_USAGE_PAYLOAD_INVALID);
		}
	}

	private String normalizeIdempotencyKey(String idempotencyKey) {
		if (!StringUtils.hasText(idempotencyKey)) {
			return null;
		}

		return idempotencyKey.trim();
	}

	private Long normalizeToken(Long token) {
		if (token == null) {
			return 0L;
		}
		if (token < 0) {
			throw BusinessException.of(ErrorCode.BILLING_USAGE_TOKEN_INVALID);
		}

		return token;
	}

	private String normalizeModelName(String modelName) {
		if (!StringUtils.hasText(modelName)) {
			return DEFAULT_MODEL_NAME;
		}

		return modelName.trim();
	}

	private LocalDateTime parseReportedAt(String timestamp) {
		if (!StringUtils.hasText(timestamp)) {
			return LocalDateTime.now();
		}

		String trimmedTimestamp = timestamp.trim();
		try {
			return OffsetDateTime.parse(trimmedTimestamp).toLocalDateTime();
		} catch (DateTimeParseException ignored) {
			return parseLocalDateTime(trimmedTimestamp);
		}
	}

	private LocalDateTime parseLocalDateTime(String timestamp) {
		try {
			return LocalDateTime.parse(timestamp);
		} catch (DateTimeParseException exception) {
			throw BusinessException.of(ErrorCode.BILLING_USAGE_PAYLOAD_INVALID, exception);
		}
	}

	private String convertUsagePayloadJson(BillingUsageMetricsRequest usage) {
		try {
			return objectMapper.writeValueAsString(usage);
		} catch (JsonProcessingException exception) {
			throw BusinessException.of(ErrorCode.BILLING_USAGE_PAYLOAD_INVALID, exception);
		}
	}
}
