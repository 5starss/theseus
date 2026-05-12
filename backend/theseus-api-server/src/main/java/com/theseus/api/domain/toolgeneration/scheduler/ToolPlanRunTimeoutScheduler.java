package com.theseus.api.domain.toolgeneration.scheduler;

import com.theseus.api.domain.toolgeneration.config.ToolGenerationStateProperties;
import com.theseus.api.domain.toolgeneration.service.ToolPlanRunRecoveryService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Slf4j
@RequiredArgsConstructor
@Component
public class ToolPlanRunTimeoutScheduler {

	private final ToolPlanRunRecoveryService toolPlanRunRecoveryService;
	private final ToolGenerationStateProperties properties;

	/**
	 * 응답 없이 제한 시간을 넘긴 ToolPlanRun을 주기적으로 실패 처리합니다.
	 */
	@Scheduled(
		initialDelayString = "${theseus.tool-generation.run-timeout-check-delay-millis:60000}",
		fixedDelayString = "${theseus.tool-generation.run-timeout-check-delay-millis:60000}"
	)
	public void failTimedOutRuns() {
		if (!properties.isRunTimeoutSchedulerEnabled()) {
			return;
		}

		int failedCount = toolPlanRunRecoveryService.failTimedOutRuns(
			properties.runTimeout(),
			properties.runTimeoutBatchSize()
		);
		if (failedCount > 0) {
			log.warn(">>>> ToolPlanRun timeout recovery completed. failedCount={}", failedCount);
		}
	}
}
