package com.theseus.api.domain.tool.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.tool.dto.response.InternalToolDraftResponse;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolStatus;
import com.theseus.api.domain.tool.repository.ToolRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class InternalToolDraftService {

	private final ToolRepository toolRepository;
	private final ObjectMapper objectMapper;

	/**
	 * 내부 서버가 재생성에 사용할 최신 Tool Draft 정보를 조회합니다.
	 */
	public InternalToolDraftResponse getToolDraft(Long toolId) {
		Tool tool = toolRepository.findByIdAndStatusNot(toolId, ToolStatus.DELETED)
			.orElseThrow(() -> BusinessException.of(ErrorCode.TOOL_NOT_FOUND));

		return InternalToolDraftResponse.createOf(
			tool,
			readJson(tool.getStructuredPlanJson()),
			readJson(tool.getDraftSnapshot())
		);
	}

	private JsonNode readJson(String value) {
		if (value == null || value.isBlank()) {
			return objectMapper.createObjectNode();
		}

		try {
			return objectMapper.readTree(value);
		} catch (JsonProcessingException exception) {
			throw BusinessException.of(ErrorCode.INTERNAL_SERVER_ERROR, exception);
		}
	}
}
