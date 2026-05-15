package com.theseus.api.domain.toolgeneration.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.chat.entity.ChatMessageContentType;
import com.theseus.api.domain.chat.entity.ChatMessageSenderType;
import com.theseus.api.domain.chat.entity.ChatMessageType;
import com.theseus.api.domain.chat.service.ChatMessageService;
import com.theseus.api.domain.project.entity.ProjectAccessLevelPolicy;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolPlan;
import com.theseus.api.domain.tool.entity.ToolPlanGroup;
import com.theseus.api.domain.tool.entity.ToolPlanGroupStatus;
import com.theseus.api.domain.tool.entity.ToolPlanRun;
import com.theseus.api.domain.tool.entity.ToolPlanRunRequestType;
import com.theseus.api.domain.tool.entity.ToolPlanStatus;
import com.theseus.api.domain.tool.entity.ToolStatus;
import com.theseus.api.domain.tool.repository.ToolPlanRunRepository;
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.toolgeneration.dto.ToolPlanRunState;
import com.theseus.api.domain.toolgeneration.event.ToolBuildArtifactPayload;
import com.theseus.api.domain.toolgeneration.event.ToolBuildEvent;
import java.time.LocalDateTime;
import java.time.OffsetDateTime;
import java.time.format.DateTimeParseException;
import java.util.Objects;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ToolBuildEventService {

	private static final String DEFAULT_FAILED_CODE = "TOOL_BUILD_FAILED";
	private static final String EVENT_TYPE_PROGRESS = "progress";
	private static final String EVENT_TYPE_CHUNK = "chunk";
	private static final String EVENT_TYPE_COMPLETED = "completed";
	private static final String EVENT_TYPE_FAILED = "failed";
	private static final String STATUS_BUILDING = "BUILDING";
	private static final String STATUS_BUILT = "BUILT";
	private static final String STATUS_FAILED = "FAILED";
	private static final String COMPLETED_MESSAGE = "Tool build completed.";
	private static final String DEFAULT_FAILED_MESSAGE = "Tool build에 실패했습니다.";

	private final ToolPlanRunRepository toolPlanRunRepository;
	private final ToolRepository toolRepository;
	private final ChatMessageService chatMessageService;
	private final ObjectMapper objectMapper;
	private final ToolPlanRunStatePublisher toolPlanRunStatePublisher;

	/**
	 * Core build 완료 이벤트를 실제 Tool 산출물로 저장하고 run/group 상태를 완료 처리합니다.
	 */
	@Transactional
	public void handleCompleted(ToolBuildEvent event) {
		toolPlanRunRepository.findByRunIdForUpdate(event.getRunId()).ifPresentOrElse(
			toolPlanRun -> handleCompletedEvent(event, toolPlanRun),
			() -> log.warn(">>>> ToolBuild completed event skipped. runId={} not found.", event.getRunId())
		);
	}

	/**
	 * Core build 실패 이벤트를 run/group 실패 상태와 System Notice로 기록합니다.
	 */
	@Transactional
	public void handleFailed(ToolBuildEvent event) {
		toolPlanRunRepository.findByRunIdForUpdate(event.getRunId()).ifPresentOrElse(
			toolPlanRun -> handleFailedEvent(event, toolPlanRun),
			() -> log.warn(">>>> ToolBuild failed event skipped. runId={} not found.", event.getRunId())
		);
	}

	/**
	 * Core build progress 이벤트를 runId 기준 Redis 상태와 SSE 이벤트로 전달합니다.
	 */
	@Transactional
	public void handleProgress(ToolBuildEvent event) {
		toolPlanRunRepository.findByRunIdForUpdate(event.getRunId()).ifPresentOrElse(
			toolPlanRun -> {
				if (shouldSkipEvent(event, toolPlanRun, "progress")) {
					return;
				}
				toolPlanRun.startGeneratingIfRequested();
				toolPlanRun.updateLastEvent(event.getEventType(), event.getEventSequence());
				toolPlanRunStatePublisher.publishProgress(createBuildProgressState(event, toolPlanRun));
			},
			() -> log.warn(">>>> ToolBuild progress event skipped. runId={} not found.", event.getRunId())
		);
	}

	/**
	 * Core build chunk 이벤트를 runId 기준 Redis 상태와 SSE 이벤트로 전달합니다.
	 */
	@Transactional
	public void handleChunk(ToolBuildEvent event) {
		toolPlanRunRepository.findByRunIdForUpdate(event.getRunId()).ifPresentOrElse(
			toolPlanRun -> {
				if (shouldSkipEvent(event, toolPlanRun, "chunk")) {
					return;
				}
				toolPlanRun.startGeneratingIfRequested();
				toolPlanRun.updateLastEvent(event.getEventType(), event.getEventSequence());
				toolPlanRunStatePublisher.publishChunk(createBuildChunkState(event, toolPlanRun));
			},
			() -> log.warn(">>>> ToolBuild chunk event skipped. runId={} not found.", event.getRunId())
		);
	}

	private void handleCompletedEvent(ToolBuildEvent event, ToolPlanRun toolPlanRun) {
		if (shouldSkipEvent(event, toolPlanRun, "completed")) {
			return;
		}

		ToolPlan toolPlan = requireBuildToolPlan(toolPlanRun, event);
		ToolBuildArtifactPayload artifact = requireArtifact(event);
		if (!ToolPlanStatus.APPROVED.equals(toolPlan.getStatus())) {
			String code = ErrorCode.TOOL_BUILD_EVENT_INVALID.getCode();
			String message = ErrorCode.TOOL_BUILD_EVENT_INVALID.getMessage();
			failBuildRun(
				toolPlanRun,
				event,
				ErrorCode.TOOL_BUILD_EVENT_INVALID.getCode(),
				"Approved ToolPlan만 Tool build 결과를 반영할 수 있습니다.",
				parseCompletedAt(event)
			);
			toolPlanRunStatePublisher.publishFailedAfterCommit(
				createBuildFailedState(event, toolPlanRun, toolPlan, code, message)
			);
			return;
		}

		Tool existingTool = toolRepository.findBySourceToolPlan(toolPlan).orElse(null);
		if (existingTool != null) {
			completeBuildWithTool(toolPlanRun, event, toolPlan, existingTool, parseCompletedAt(event));
			toolPlanRunStatePublisher.publishCompletedAfterCommit(createBuildCompletedState(event, toolPlanRun, toolPlan));
			log.info(
				">>>> ToolBuild completed event skipped by existing Tool. runId={}, toolId={}",
				event.getRunId(),
				existingTool.getId()
			);
			return;
		}

		String fileName = requireText(artifact.getFileName());
		if (toolRepository.existsByProjectAndFileName(toolPlan.getProject(), fileName)) {
			String code = ErrorCode.DUPLICATE_TOOL_FILE_NAME.getCode();
			String message = createDuplicateFileNameFailureMessage(fileName);
			failBuildRun(
				toolPlanRun,
				event,
				code,
				message,
				parseCompletedAt(event)
			);
			toolPlanRunStatePublisher.publishFailedAfterCommit(
				createBuildFailedState(event, toolPlanRun, toolPlan, code, message)
			);
			return;
		}

		Tool createdTool = toolRepository.save(Tool.builder()
			.project(toolPlan.getProject())
			.chatSession(toolPlan.getChatSession())
			.createdByProjectMember(toolPlan.getCreatedByProjectMember())
			.sourceToolPlan(toolPlan)
			.fileName(fileName)
			.displayName(resolveDisplayName(artifact, fileName))
			.displayDescription(artifact.getDisplayDescription())
			.status(ToolStatus.APPROVED)
			.toolGrade(ProjectAccessLevelPolicy.ADMIN_ACCESS_LEVEL)
			.moduleName(artifact.getModuleName())
			.artifactPath(artifact.getArtifactPath())
			.codeSnapshot(artifact.getCodeSnapshot())
			.metadataJson(writeJsonNodeAsString(artifact.getMetadataJson()))
			.build());

		completeBuildWithTool(toolPlanRun, event, toolPlan, createdTool, parseCompletedAt(event));
		toolPlanRunStatePublisher.publishCompletedAfterCommit(createBuildCompletedState(event, toolPlanRun, toolPlan));
		log.info(
			">>>> ToolBuild completed event handled. runId={}, toolPlanId={}, toolId={}",
			event.getRunId(),
			toolPlan.getId(),
			createdTool.getId()
		);
	}

	private void handleFailedEvent(ToolBuildEvent event, ToolPlanRun toolPlanRun) {
		if (shouldSkipEvent(event, toolPlanRun, "failed")) {
			return;
		}

		ToolPlan toolPlan = requireBuildToolPlan(toolPlanRun, event);
		String code = resolveCode(event.getCode());
		String message = resolveFailedMessage(event.getMessage());
		failBuildRun(
			toolPlanRun,
			event,
			code,
			message,
			parseFailedAt(event)
		);
		toolPlanRunStatePublisher.publishFailedAfterCommit(
			createBuildFailedState(event, toolPlanRun, toolPlan, code, message)
		);
		log.warn(
			">>>> ToolBuild failed event handled. runId={}, code={}",
			event.getRunId(),
			code
		);
	}

	private boolean shouldSkipEvent(ToolBuildEvent event, ToolPlanRun toolPlanRun, String eventName) {
		if (!ToolPlanRunRequestType.BUILD_TOOL.equals(toolPlanRun.getRequestType())) {
			log.warn(">>>> ToolBuild {} event target run type mismatch. runId={}", eventName, event.getRunId());
			return true;
		}
		if (!hasSameProjectAndSession(event, toolPlanRun)) {
			log.warn(">>>> ToolBuild {} event target mismatch. runId={}", eventName, event.getRunId());
			return true;
		}
		if (toolPlanRun.isFinished()) {
			log.info(">>>> ToolBuild {} event skipped by terminal run. runId={}", eventName, event.getRunId());
			return true;
		}
		if (shouldSkipProcessedEventSequence(event, toolPlanRun, eventName)) {
			return true;
		}
		return false;
	}

	private boolean shouldSkipProcessedEventSequence(ToolBuildEvent event, ToolPlanRun toolPlanRun, String eventName) {
		if (!toolPlanRun.hasProcessedEventSequence(event.getEventSequence())) {
			return false;
		}

		log.info(
			">>>> ToolBuild {} event skipped by processed sequence. runId={}, eventSequence={}, lastEventSequence={}",
			eventName,
			event.getRunId(),
			event.getEventSequence(),
			toolPlanRun.getLastEventSequence()
		);
		return true;
	}

	private ToolPlanRunState createBuildProgressState(ToolBuildEvent event, ToolPlanRun toolPlanRun) {
		return createBaseState(event, toolPlanRun)
			.eventType(EVENT_TYPE_PROGRESS)
			.status(STATUS_BUILDING)
			.progressRate(event.getProgressRate())
			.message(event.getMessage())
			.build();
	}

	private ToolPlanRunState createBuildChunkState(ToolBuildEvent event, ToolPlanRun toolPlanRun) {
		return createBaseState(event, toolPlanRun)
			.eventType(EVENT_TYPE_CHUNK)
			.status(STATUS_BUILDING)
			.content(event.getContent())
			.build();
	}

	private ToolPlanRunState createBuildCompletedState(
		ToolBuildEvent event,
		ToolPlanRun toolPlanRun,
		ToolPlan toolPlan
	) {
		return createBaseState(event, toolPlanRun)
			.toolPlanGroupId(toolPlan.getPlanGroup().getId())
			.toolPlanId(toolPlan.getId())
			.planVersion(toolPlan.getPlanVersion())
			.eventType(EVENT_TYPE_COMPLETED)
			.status(STATUS_BUILT)
			.message(COMPLETED_MESSAGE)
			.build();
	}

	private ToolPlanRunState createBuildFailedState(
		ToolBuildEvent event,
		ToolPlanRun toolPlanRun,
		ToolPlan toolPlan,
		String code,
		String message
	) {
		return createBaseState(event, toolPlanRun)
			.toolPlanGroupId(toolPlan.getPlanGroup().getId())
			.toolPlanId(toolPlan.getId())
			.planVersion(toolPlan.getPlanVersion())
			.eventType(EVENT_TYPE_FAILED)
			.status(STATUS_FAILED)
			.message(message)
			.errorCode(code)
			.errorMessage(message)
			.build();
	}

	private ToolPlanRunState.ToolPlanRunStateBuilder createBaseState(ToolBuildEvent event, ToolPlanRun toolPlanRun) {
		ToolPlan baseToolPlan = toolPlanRun.getBaseToolPlan();
		ToolPlanGroup planGroup = toolPlanRun.getPlanGroup();
		if (planGroup == null && baseToolPlan != null) {
			planGroup = baseToolPlan.getPlanGroup();
		}

		return ToolPlanRunState.builder()
			.runId(toolPlanRun.getRunId())
			.projectId(event.getProjectId())
			.chatSessionId(event.getChatSessionId())
			.toolPlanGroupId(planGroup == null ? null : planGroup.getId())
			.toolPlanId(baseToolPlan == null ? null : baseToolPlan.getId())
			.planVersion(baseToolPlan == null ? null : baseToolPlan.getPlanVersion())
			.updatedAt(LocalDateTime.now());
	}

	private ToolPlan requireBuildToolPlan(ToolPlanRun toolPlanRun, ToolBuildEvent event) {
		ToolPlan toolPlan = toolPlanRun.getBaseToolPlan();
		if (toolPlan == null || !Objects.equals(toolPlan.getId(), event.getToolPlanId())) {
			throw BusinessException.of(ErrorCode.TOOL_BUILD_EVENT_INVALID);
		}
		return toolPlan;
	}

	private ToolBuildArtifactPayload requireArtifact(ToolBuildEvent event) {
		if (event.getArtifact() == null) {
			throw BusinessException.of(ErrorCode.TOOL_BUILD_EVENT_INVALID);
		}
		return event.getArtifact();
	}

	private void completeBuildWithTool(
		ToolPlanRun toolPlanRun,
		ToolBuildEvent event,
		ToolPlan toolPlan,
		Tool tool,
		LocalDateTime completedAt
	) {
		completePlanGroupBuild(toolPlan.getPlanGroup(), tool);
		toolPlanRun.complete(toolPlan, completedAt);
		toolPlanRun.updateLastEvent(event.getEventType(), event.getEventSequence());
		chatMessageService.saveToolPlanEventMessage(
			toolPlanRun.getChatSession(),
			toolPlan,
			toolPlanRun,
			ChatMessageSenderType.SYSTEM,
			ChatMessageType.TOOL_BUILD_NOTICE,
			ChatMessageContentType.JSON,
			createCompletedNoticeContent(event, tool),
			createIdempotencyKey(event, "system")
		);
	}

	private void completePlanGroupBuild(ToolPlanGroup planGroup, Tool tool) {
		if (ToolPlanGroupStatus.APPROVED.equals(planGroup.getStatus())) {
			planGroup.startBuilding();
		}
		if (ToolPlanGroupStatus.BUILDING.equals(planGroup.getStatus())) {
			planGroup.completeBuild(tool);
			return;
		}
		if (ToolPlanGroupStatus.BUILT.equals(planGroup.getStatus())
			&& planGroup.getCreatedTool() != null
			&& Objects.equals(planGroup.getCreatedTool().getId(), tool.getId())) {
			return;
		}

		throw BusinessException.of(ErrorCode.TOOL_PLAN_STATUS_TRANSITION_INVALID);
	}

	private void failBuildRun(
		ToolPlanRun toolPlanRun,
		ToolBuildEvent event,
		String code,
		String message,
		LocalDateTime failedAt
	) {
		ToolPlanGroup planGroup = toolPlanRun.getPlanGroup();
		if (planGroup != null && !planGroup.isFinished()) {
			planGroup.fail();
		}
		toolPlanRun.fail(code, message, failedAt);
		toolPlanRun.updateLastEvent(event.getEventType(), event.getEventSequence());
		chatMessageService.saveToolPlanEventMessage(
			toolPlanRun.getChatSession(),
			toolPlanRun.getBaseToolPlan(),
			toolPlanRun,
			ChatMessageSenderType.SYSTEM,
			ChatMessageType.SYSTEM_NOTICE,
			ChatMessageContentType.TEXT,
			createFailedNoticeMessage(code, message),
			createIdempotencyKey(event, "system")
		);
	}

	private String createCompletedNoticeContent(ToolBuildEvent event, Tool tool) {
		return """
			{"runId":"%s","toolPlanId":%d,"toolId":%d,"status":"BUILT","fileName":"%s"}
			""".formatted(
			event.getRunId(),
			event.getToolPlanId(),
			tool.getId(),
			tool.getFileName()
		).trim();
	}

	private String createFailedNoticeMessage(String code, String message) {
		return DEFAULT_FAILED_MESSAGE + " code=" + code + ", message=" + message;
	}

	private String createDuplicateFileNameFailureMessage(String fileName) {
		return ErrorCode.DUPLICATE_TOOL_FILE_NAME.getMessage() + "\n\n"
			+ "원인: 같은 프로젝트에 `" + fileName + "` 파일명을 사용하는 Tool이 이미 있습니다.\n"
			+ "의미: 기존 Tool artifact를 실수로 덮어쓰지 않도록 API Server가 저장을 차단했습니다.\n"
			+ "다음 선택지: 기존 Tool을 재사용하거나, 기존 Tool을 개선하는 승인 흐름으로 전환하거나, "
			+ "새 toolName/moduleName/fileName으로 다시 생성해야 합니다.\n"
			+ "재요청 예시: `기존 Tool과 충돌하지 않도록 새 이름으로 생성해줘. "
			+ "기존 Tool이 있으면 재사용/확장 여부도 같이 제안해줘.`";
	}

	private String resolveDisplayName(ToolBuildArtifactPayload artifact, String fileName) {
		if (artifact.getDisplayName() != null && !artifact.getDisplayName().isBlank()) {
			return artifact.getDisplayName();
		}
		return fileName;
	}

	private String requireText(String value) {
		if (value == null || value.isBlank()) {
			throw BusinessException.of(ErrorCode.TOOL_BUILD_EVENT_INVALID);
		}
		return value;
	}

	private String writeJsonNodeAsString(JsonNode jsonNode) {
		if (jsonNode == null || jsonNode.isNull()) {
			return null;
		}

		try {
			return objectMapper.writeValueAsString(jsonNode);
		} catch (JsonProcessingException exception) {
			throw BusinessException.of(ErrorCode.TOOL_BUILD_EVENT_INVALID, exception);
		}
	}

	private boolean hasSameProjectAndSession(ToolBuildEvent event, ToolPlanRun toolPlanRun) {
		return Objects.equals(event.getProjectId(), toolPlanRun.getProject().getId())
			&& Objects.equals(event.getChatSessionId(), toolPlanRun.getChatSession().getId());
	}

	private LocalDateTime parseCompletedAt(ToolBuildEvent event) {
		return parseDateTime(event.getCompletedAt());
	}

	private LocalDateTime parseFailedAt(ToolBuildEvent event) {
		return parseDateTime(event.getFailedAt());
	}

	private LocalDateTime parseDateTime(String value) {
		if (value == null || value.isBlank()) {
			return LocalDateTime.now();
		}

		try {
			return OffsetDateTime.parse(value).toLocalDateTime();
		} catch (DateTimeParseException ignored) {
			try {
				return LocalDateTime.parse(value);
			} catch (DateTimeParseException exception) {
				log.warn(">>>> ToolBuild event datetime parse failed. value={}", value);
				return LocalDateTime.now();
			}
		}
	}

	private String createIdempotencyKey(ToolBuildEvent event, String suffix) {
		return "tool-build-event:" + event.getRunId() + ":" + event.getEventType() + ":" + suffix;
	}

	private String resolveCode(String code) {
		if (code == null || code.isBlank()) {
			return DEFAULT_FAILED_CODE;
		}
		return code;
	}

	private String resolveFailedMessage(String message) {
		if (message == null || message.isBlank()) {
			return DEFAULT_FAILED_MESSAGE;
		}
		return message;
	}
}
