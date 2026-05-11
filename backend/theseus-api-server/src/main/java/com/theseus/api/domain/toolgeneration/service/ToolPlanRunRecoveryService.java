package com.theseus.api.domain.toolgeneration.service;

import com.theseus.api.domain.chat.entity.ChatMessageContentType;
import com.theseus.api.domain.chat.entity.ChatMessageSenderType;
import com.theseus.api.domain.chat.entity.ChatMessageType;
import com.theseus.api.domain.chat.service.ChatMessageService;
import com.theseus.api.domain.tool.entity.ToolPlan;
import com.theseus.api.domain.tool.entity.ToolPlanGroup;
import com.theseus.api.domain.tool.entity.ToolPlanRun;
import com.theseus.api.domain.tool.entity.ToolPlanRunRequestType;
import com.theseus.api.domain.tool.entity.ToolPlanRunStatus;
import com.theseus.api.domain.tool.repository.ToolPlanRunRepository;
import com.theseus.api.domain.toolgeneration.dto.ToolPlanRunState;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@RequiredArgsConstructor
@Service
public class ToolPlanRunRecoveryService {

	private static final String TIMEOUT_ERROR_CODE = "TOOL_PLAN_RUN_TIMEOUT";
	private static final String TIMEOUT_MESSAGE = "ToolPlanRun 처리 시간이 초과되었습니다.";
	private static final String EVENT_TYPE_FAILED = "failed";
	private static final String STATUS_FAILED = "FAILED";

	private final ToolPlanRunRepository toolPlanRunRepository;
	private final ChatMessageService chatMessageService;
	private final ToolPlanRunStatePublisher toolPlanRunStatePublisher;

	/**
	 * 제한 시간을 넘긴 REQUESTED/GENERATING Run을 실패 처리합니다.
	 */
	@Transactional
	public int failTimedOutRuns(Duration timeout) {
		if (timeout == null || timeout.isZero() || timeout.isNegative()) {
			log.warn(">>>> ToolPlanRun timeout recovery skipped. invalidTimeout={}", timeout);
			return 0;
		}

		LocalDateTime cutoff = LocalDateTime.now().minus(timeout);
		List<ToolPlanRun> timedOutRuns = toolPlanRunRepository.findTimedOutRunsForUpdate(
			List.of(ToolPlanRunStatus.REQUESTED, ToolPlanRunStatus.GENERATING),
			cutoff
		);

		timedOutRuns.forEach(this::failTimedOutRun);
		return timedOutRuns.size();
	}

	private void failTimedOutRun(ToolPlanRun toolPlanRun) {
		failBuildGroupIfNeeded(toolPlanRun);
		toolPlanRun.fail(TIMEOUT_ERROR_CODE, TIMEOUT_MESSAGE, LocalDateTime.now());
		chatMessageService.saveToolPlanEventMessage(
			toolPlanRun.getChatSession(),
			toolPlanRun.getBaseToolPlan(),
			toolPlanRun,
			ChatMessageSenderType.SYSTEM,
			ChatMessageType.SYSTEM_NOTICE,
			ChatMessageContentType.TEXT,
			createTimeoutNoticeMessage(),
			createTimeoutIdempotencyKey(toolPlanRun)
		);
		toolPlanRunStatePublisher.publishFailedAfterCommit(createFailedState(toolPlanRun));
		log.warn(">>>> ToolPlanRun timeout handled. runId={}", toolPlanRun.getRunId());
	}

	private void failBuildGroupIfNeeded(ToolPlanRun toolPlanRun) {
		ToolPlanGroup planGroup = toolPlanRun.getPlanGroup();
		if (!ToolPlanRunRequestType.BUILD_TOOL.equals(toolPlanRun.getRequestType())
			|| planGroup == null
			|| planGroup.isFinished()) {
			return;
		}

		planGroup.fail();
	}

	private ToolPlanRunState createFailedState(ToolPlanRun toolPlanRun) {
		ToolPlan baseToolPlan = toolPlanRun.getBaseToolPlan();
		ToolPlanGroup planGroup = toolPlanRun.getPlanGroup();
		if (planGroup == null && baseToolPlan != null) {
			planGroup = baseToolPlan.getPlanGroup();
		}

		return ToolPlanRunState.builder()
			.runId(toolPlanRun.getRunId())
			.projectId(toolPlanRun.getProject().getId())
			.chatSessionId(toolPlanRun.getChatSession().getId())
			.toolPlanGroupId(planGroup == null ? null : planGroup.getId())
			.toolPlanId(baseToolPlan == null ? null : baseToolPlan.getId())
			.planVersion(baseToolPlan == null ? null : baseToolPlan.getPlanVersion())
			.eventType(EVENT_TYPE_FAILED)
			.status(STATUS_FAILED)
			.message(TIMEOUT_MESSAGE)
			.errorCode(TIMEOUT_ERROR_CODE)
			.errorMessage(TIMEOUT_MESSAGE)
			.updatedAt(LocalDateTime.now())
			.build();
	}

	private String createTimeoutNoticeMessage() {
		return TIMEOUT_MESSAGE + " code=" + TIMEOUT_ERROR_CODE + ", message=" + TIMEOUT_MESSAGE;
	}

	private String createTimeoutIdempotencyKey(ToolPlanRun toolPlanRun) {
		return "tool-plan-run-timeout:" + toolPlanRun.getRunId() + ":system";
	}
}
