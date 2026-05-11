package com.theseus.api.domain.toolgeneration.service;

import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.tool.entity.ToolPlanRun;
import com.theseus.api.domain.toolgeneration.dto.response.ToolPlanRunStateResponse;
import com.theseus.api.domain.toolgeneration.redis.ToolPlanRunStateStore;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ToolPlanRunStateService {

	private final ToolPlanRunAccessService toolPlanRunAccessService;
	private final ToolPlanRunStateStore toolPlanRunStateStore;

	/**
	 * Redis 최신 상태를 우선 조회하고 없으면 ToolPlanRun DB 상태로 진행 상태를 복구합니다.
	 */
	public ToolPlanRunStateResponse getToolPlanRunState(
		AuthenticatedUser currentUser,
		Long projectId,
		Long chatSessionId,
		String runId
	) {
		ToolPlanRun toolPlanRun = toolPlanRunAccessService.getAccessibleRun(
			currentUser,
			projectId,
			chatSessionId,
			runId
		);

		try {
			return toolPlanRunStateStore.findByRunId(toolPlanRun.getRunId())
				.map(ToolPlanRunStateResponse::createFrom)
				.orElseGet(() -> ToolPlanRunStateResponse.createFallbackFrom(toolPlanRun));
		} catch (RuntimeException exception) {
			log.warn(
				">>>> Failed to find ToolPlanRun Redis state. projectId={}, chatSessionId={}, runId={}",
				projectId,
				chatSessionId,
				runId,
				exception
			);
			return ToolPlanRunStateResponse.createFallbackFrom(toolPlanRun);
		}
	}
}
