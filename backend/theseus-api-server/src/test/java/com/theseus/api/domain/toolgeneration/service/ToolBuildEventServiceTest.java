package com.theseus.api.domain.toolgeneration.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.argThat;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.same;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.chat.entity.ChatMessageContentType;
import com.theseus.api.domain.chat.entity.ChatMessageSenderType;
import com.theseus.api.domain.chat.entity.ChatMessageType;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.chat.service.ChatMessageService;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectAccessLevelPolicy;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolPlan;
import com.theseus.api.domain.tool.entity.ToolPlanGroup;
import com.theseus.api.domain.tool.entity.ToolPlanGroupStatus;
import com.theseus.api.domain.tool.entity.ToolPlanRun;
import com.theseus.api.domain.tool.entity.ToolPlanRunRequestType;
import com.theseus.api.domain.tool.entity.ToolPlanRunStatus;
import com.theseus.api.domain.tool.entity.ToolPlanStatus;
import com.theseus.api.domain.tool.entity.ToolStatus;
import com.theseus.api.domain.tool.repository.ToolPlanRunRepository;
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.toolgeneration.dto.ToolPlanRunState;
import com.theseus.api.domain.toolgeneration.event.ToolBuildArtifactPayload;
import com.theseus.api.domain.toolgeneration.event.ToolBuildEvent;
import com.theseus.api.domain.user.entity.User;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class ToolBuildEventServiceTest {

	private static final Long PROJECT_ID = 10L;
	private static final Long CHAT_SESSION_ID = 30L;
	private static final Long TOOL_PLAN_ID = 50L;
	private static final String RUN_ID = "build-run-253";

	@Mock
	private ToolPlanRunRepository toolPlanRunRepository;

	@Mock
	private ToolRepository toolRepository;

	@Mock
	private ChatMessageService chatMessageService;

	@Mock
	private ToolPlanRunStatePublisher toolPlanRunStatePublisher;

	private ObjectMapper objectMapper;
	private ToolBuildEventService toolBuildEventService;

	@BeforeEach
	void setUp() {
		objectMapper = new ObjectMapper();
		toolBuildEventService = new ToolBuildEventService(
			toolPlanRunRepository,
			toolRepository,
			chatMessageService,
			objectMapper,
			toolPlanRunStatePublisher
		);
	}

	@Test
	@DisplayName("build completed 이벤트는 승인된 ToolPlan 기반 Tool을 생성하고 run/group을 완료 처리한다")
	void handleCompletedCreatesToolFromApprovedToolPlan() throws Exception {
		// Given
		TestFixture fixture = createApprovedBuildFixture();
		ToolPlanRun buildRun = createBuildRun(fixture);
		ToolBuildEvent event = createCompletedEvent();
		when(toolPlanRunRepository.findByRunIdForUpdate(RUN_ID)).thenReturn(Optional.of(buildRun));
		when(toolRepository.findBySourceToolPlan(fixture.toolPlan())).thenReturn(Optional.empty());
		when(toolRepository.existsByProjectAndFileName(fixture.project(), "incident_recovery.py")).thenReturn(false);
		when(toolRepository.save(any(Tool.class))).thenAnswer(invocation -> {
			Tool savedTool = invocation.getArgument(0);
			ReflectionTestUtils.setField(savedTool, "id", 900L);
			return savedTool;
		});

		// When
		toolBuildEventService.handleCompleted(event);

		// Then
		ArgumentCaptor<Tool> toolCaptor = ArgumentCaptor.forClass(Tool.class);
		verify(toolRepository).save(toolCaptor.capture());
		Tool savedTool = toolCaptor.getValue();
		assertThat(savedTool.getProject()).isEqualTo(fixture.project());
		assertThat(savedTool.getChatSession()).isEqualTo(fixture.chatSession());
		assertThat(savedTool.getCreatedByProjectMember()).isEqualTo(fixture.creator());
		assertThat(savedTool.getSourceToolPlan()).isEqualTo(fixture.toolPlan());
		assertThat(savedTool.getFileName()).isEqualTo("incident_recovery.py");
		assertThat(savedTool.getDisplayName()).isEqualTo("Incident Recovery");
		assertThat(savedTool.getDisplayDescription()).isEqualTo("Builds recovery guide.");
		assertThat(savedTool.getStatus()).isEqualTo(ToolStatus.APPROVED);
		assertThat(savedTool.getToolGrade()).isEqualTo(ProjectAccessLevelPolicy.ADMIN_ACCESS_LEVEL);
		assertThat(savedTool.getModuleName()).isEqualTo("incident_recovery");
		assertThat(savedTool.getArtifactPath()).isEqualTo("projects/10/incident_recovery.py");
		assertThat(savedTool.getCodeSnapshot()).isEqualTo("print('ok')");
		assertThat(savedTool.getMetadataJson()).isEqualTo("{\"toolName\":\"incident_recovery\"}");

		assertThat(buildRun.getStatus()).isEqualTo(ToolPlanRunStatus.COMPLETED);
		assertThat(buildRun.getResultToolPlan()).isEqualTo(fixture.toolPlan());
		assertThat(fixture.planGroup().getStatus()).isEqualTo(ToolPlanGroupStatus.BUILT);
		assertThat(fixture.planGroup().getCreatedTool()).isEqualTo(savedTool);
		verify(chatMessageService).saveToolPlanEventMessage(
			same(fixture.chatSession()),
			same(fixture.toolPlan()),
			same(buildRun),
			eq(ChatMessageSenderType.SYSTEM),
			eq(ChatMessageType.TOOL_BUILD_NOTICE),
			eq(ChatMessageContentType.JSON),
			eq("""
				{"runId":"build-run-253","toolPlanId":50,"toolId":900,"status":"BUILT","fileName":"incident_recovery.py"}
				""".trim()),
			eq("tool-build-event:build-run-253:TOOL_BUILD_COMPLETED:system")
		);
	}

	@Test
	@DisplayName("같은 ToolPlan으로 이미 생성된 Tool이 있으면 Tool을 중복 생성하지 않는다")
	void handleCompletedSkipsDuplicateSourceTool() throws Exception {
		// Given
		TestFixture fixture = createApprovedBuildFixture();
		ToolPlanRun buildRun = createBuildRun(fixture);
		Tool existingTool = createBuiltTool(fixture);
		ToolBuildEvent event = createCompletedEvent();
		when(toolPlanRunRepository.findByRunIdForUpdate(RUN_ID)).thenReturn(Optional.of(buildRun));
		when(toolRepository.findBySourceToolPlan(fixture.toolPlan())).thenReturn(Optional.of(existingTool));

		// When
		toolBuildEventService.handleCompleted(event);

		// Then
		verify(toolRepository, never()).save(any(Tool.class));
		assertThat(buildRun.getStatus()).isEqualTo(ToolPlanRunStatus.COMPLETED);
		assertThat(fixture.planGroup().getStatus()).isEqualTo(ToolPlanGroupStatus.BUILT);
		assertThat(fixture.planGroup().getCreatedTool()).isEqualTo(existingTool);
	}

	@Test
	@DisplayName("fileName이 이미 존재하면 Tool을 만들지 않고 build run을 실패 처리한다")
	void handleCompletedFailsWhenFileNameDuplicated() throws Exception {
		// Given
		TestFixture fixture = createApprovedBuildFixture();
		ToolPlanRun buildRun = createBuildRun(fixture);
		ToolBuildEvent event = createCompletedEvent();
		when(toolPlanRunRepository.findByRunIdForUpdate(RUN_ID)).thenReturn(Optional.of(buildRun));
		when(toolRepository.findBySourceToolPlan(fixture.toolPlan())).thenReturn(Optional.empty());
		when(toolRepository.existsByProjectAndFileName(fixture.project(), "incident_recovery.py")).thenReturn(true);

		// When
		toolBuildEventService.handleCompleted(event);

		// Then
		verify(toolRepository, never()).save(any(Tool.class));
		assertThat(buildRun.getStatus()).isEqualTo(ToolPlanRunStatus.FAILED);
		assertThat(buildRun.getErrorCode()).isEqualTo(ErrorCode.DUPLICATE_TOOL_FILE_NAME.getCode());
		assertThat(fixture.planGroup().getStatus()).isEqualTo(ToolPlanGroupStatus.FAILED);
		verify(chatMessageService).saveToolPlanEventMessage(
			same(fixture.chatSession()),
			same(fixture.toolPlan()),
			same(buildRun),
			eq(ChatMessageSenderType.SYSTEM),
			eq(ChatMessageType.SYSTEM_NOTICE),
			eq(ChatMessageContentType.TEXT),
			argThat(message -> message.startsWith("Tool build에 실패했습니다. code=TOOL-008, message=이미 존재하는 Tool 파일명입니다.")
				&& message.contains("incident_recovery.py")
				&& message.contains("새 toolName/moduleName/fileName")),
			eq("tool-build-event:build-run-253:TOOL_BUILD_COMPLETED:system")
		);
	}

	@Test
	@DisplayName("build failed 이벤트는 Tool을 생성하지 않고 run/group을 실패 처리한다")
	void handleFailedDoesNotCreateTool() {
		// Given
		TestFixture fixture = createApprovedBuildFixture();
		ToolPlanRun buildRun = createBuildRun(fixture);
		ToolBuildEvent event = createFailedEvent();
		when(toolPlanRunRepository.findByRunIdForUpdate(RUN_ID)).thenReturn(Optional.of(buildRun));

		// When
		toolBuildEventService.handleFailed(event);

		// Then
		verify(toolRepository, never()).save(any(Tool.class));
		assertThat(buildRun.getStatus()).isEqualTo(ToolPlanRunStatus.FAILED);
		assertThat(buildRun.getErrorCode()).isEqualTo("TOOL_BUILD_FAILED");
		assertThat(buildRun.getErrorMessage()).isEqualTo("Tool validation failed.");
		assertThat(fixture.planGroup().getStatus()).isEqualTo(ToolPlanGroupStatus.FAILED);
		verify(chatMessageService).saveToolPlanEventMessage(
			same(fixture.chatSession()),
			same(fixture.toolPlan()),
			same(buildRun),
			eq(ChatMessageSenderType.SYSTEM),
			eq(ChatMessageType.SYSTEM_NOTICE),
			eq(ChatMessageContentType.TEXT),
			eq("Tool build에 실패했습니다. code=TOOL_BUILD_FAILED, message=Tool validation failed."),
			eq("tool-build-event:build-run-253:TOOL_BUILD_FAILED:system")
		);
	}

	@Test
	@DisplayName("project/session이 맞지 않는 이벤트는 DB 변경 없이 건너뛴다")
	void skipMismatchedProjectOrSession() throws Exception {
		// Given
		TestFixture fixture = createApprovedBuildFixture();
		ToolPlanRun buildRun = createBuildRun(fixture);
		ToolBuildEvent event = ToolBuildEvent.builder()
			.eventType("TOOL_BUILD_COMPLETED")
			.runId(RUN_ID)
			.projectId(999L)
			.chatSessionId(CHAT_SESSION_ID)
			.toolPlanId(TOOL_PLAN_ID)
			.artifact(createArtifact())
			.build();
		when(toolPlanRunRepository.findByRunIdForUpdate(RUN_ID)).thenReturn(Optional.of(buildRun));

		// When
		toolBuildEventService.handleCompleted(event);

		// Then
		assertThat(buildRun.getStatus()).isEqualTo(ToolPlanRunStatus.REQUESTED);
		verifyNoInteractions(toolRepository, chatMessageService);
	}

	@Test
	@DisplayName("이미 종료된 Run의 terminal 이벤트는 중복 처리하지 않는다")
	void skipAlreadyFinishedRun() throws Exception {
		// Given
		TestFixture fixture = createApprovedBuildFixture();
		ToolPlanRun buildRun = createBuildRun(fixture);
		Tool resultTool = createBuiltTool(fixture);
		buildRun.complete(fixture.toolPlan(), java.time.LocalDateTime.of(2026, 5, 11, 12, 0));
		fixture.planGroup().startBuilding();
		fixture.planGroup().completeBuild(resultTool);
		when(toolPlanRunRepository.findByRunIdForUpdate(RUN_ID)).thenReturn(Optional.of(buildRun));

		// When
		toolBuildEventService.handleCompleted(createCompletedEvent());

		// Then
		verifyNoInteractions(toolRepository, chatMessageService);
	}

	@Test
	@DisplayName("progress 이벤트는 runId 기준 상태로 변환해 Redis/SSE Publisher에 위임한다")
	void handleProgressPublishesRunState() {
		// Given
		TestFixture fixture = createApprovedBuildFixture();
		ToolPlanRun buildRun = createBuildRun(fixture);
		ToolBuildEvent event = ToolBuildEvent.builder()
			.eventType("progress")
			.runId(RUN_ID)
			.eventSequence(1L)
			.projectId(PROJECT_ID)
			.chatSessionId(CHAT_SESSION_ID)
			.toolPlanId(TOOL_PLAN_ID)
			.progressRate(70)
			.message("Building tool")
			.build();
		when(toolPlanRunRepository.findByRunIdForUpdate(RUN_ID)).thenReturn(Optional.of(buildRun));

		// When
		toolBuildEventService.handleProgress(event);

		// Then
		ArgumentCaptor<ToolPlanRunState> stateCaptor = ArgumentCaptor.forClass(ToolPlanRunState.class);
		verify(toolPlanRunStatePublisher).publishProgress(stateCaptor.capture());
		assertThat(stateCaptor.getValue().getRunId()).isEqualTo(RUN_ID);
		assertThat(stateCaptor.getValue().getEventType()).isEqualTo("progress");
		assertThat(stateCaptor.getValue().getStatus()).isEqualTo("BUILDING");
		assertThat(stateCaptor.getValue().getProgressRate()).isEqualTo(70);
		assertThat(buildRun.getStatus()).isEqualTo(ToolPlanRunStatus.GENERATING);
		assertThat(buildRun.getLastEventType()).isEqualTo("progress");
		assertThat(buildRun.getLastEventSequence()).isEqualTo(1L);
	}

	@Test
	@DisplayName("chunk 이벤트는 runId 기준 상태로 변환해 Redis/SSE Publisher에 위임한다")
	void handleChunkPublishesRunState() {
		// Given
		TestFixture fixture = createApprovedBuildFixture();
		ToolPlanRun buildRun = createBuildRun(fixture);
		ToolBuildEvent event = ToolBuildEvent.builder()
			.eventType("chunk")
			.runId(RUN_ID)
			.eventSequence(2L)
			.projectId(PROJECT_ID)
			.chatSessionId(CHAT_SESSION_ID)
			.toolPlanId(TOOL_PLAN_ID)
			.content("Build chunk")
			.build();
		when(toolPlanRunRepository.findByRunIdForUpdate(RUN_ID)).thenReturn(Optional.of(buildRun));

		// When
		toolBuildEventService.handleChunk(event);

		// Then
		ArgumentCaptor<ToolPlanRunState> stateCaptor = ArgumentCaptor.forClass(ToolPlanRunState.class);
		verify(toolPlanRunStatePublisher).publishChunk(stateCaptor.capture());
		assertThat(stateCaptor.getValue().getRunId()).isEqualTo(RUN_ID);
		assertThat(stateCaptor.getValue().getEventType()).isEqualTo("chunk");
		assertThat(stateCaptor.getValue().getContent()).isEqualTo("Build chunk");
		assertThat(buildRun.getStatus()).isEqualTo(ToolPlanRunStatus.GENERATING);
		assertThat(buildRun.getLastEventType()).isEqualTo("chunk");
		assertThat(buildRun.getLastEventSequence()).isEqualTo(2L);
	}

	@Test
	@DisplayName("이미 처리한 eventSequence보다 오래된 이벤트는 중복 처리하지 않는다")
	void skipStaleEventSequence() throws Exception {
		// Given
		TestFixture fixture = createApprovedBuildFixture();
		ToolPlanRun buildRun = createBuildRun(fixture);
		buildRun.updateLastEvent("progress", 10L);
		ToolBuildEvent event = ToolBuildEvent.builder()
			.eventType("TOOL_BUILD_COMPLETED")
			.runId(RUN_ID)
			.eventSequence(7L)
			.projectId(PROJECT_ID)
			.chatSessionId(CHAT_SESSION_ID)
			.toolPlanId(TOOL_PLAN_ID)
			.artifact(createArtifact())
			.completedAt("2026-05-11T10:12:00")
			.build();
		when(toolPlanRunRepository.findByRunIdForUpdate(RUN_ID)).thenReturn(Optional.of(buildRun));

		// When
		toolBuildEventService.handleCompleted(event);

		// Then
		assertThat(buildRun.getStatus()).isEqualTo(ToolPlanRunStatus.REQUESTED);
		assertThat(buildRun.getLastEventSequence()).isEqualTo(10L);
		verifyNoInteractions(toolRepository, chatMessageService, toolPlanRunStatePublisher);
	}
	private ToolBuildEvent createCompletedEvent() throws Exception {
		return ToolBuildEvent.builder()
			.eventType("TOOL_BUILD_COMPLETED")
			.runId(RUN_ID)
			.eventSequence(7L)
			.projectId(PROJECT_ID)
			.chatSessionId(CHAT_SESSION_ID)
			.toolPlanId(TOOL_PLAN_ID)
			.artifact(createArtifact())
			.completedAt("2026-05-11T10:12:00")
			.build();
	}

	private ToolBuildEvent createFailedEvent() {
		return ToolBuildEvent.builder()
			.eventType("TOOL_BUILD_FAILED")
			.runId(RUN_ID)
			.eventSequence(8L)
			.projectId(PROJECT_ID)
			.chatSessionId(CHAT_SESSION_ID)
			.toolPlanId(TOOL_PLAN_ID)
			.code("TOOL_BUILD_FAILED")
			.message("Tool validation failed.")
			.failedAt("2026-05-11T10:12:00")
			.build();
	}

	private ToolBuildArtifactPayload createArtifact() throws Exception {
		return ToolBuildArtifactPayload.builder()
			.fileName("incident_recovery.py")
			.moduleName("incident_recovery")
			.artifactPath("projects/10/incident_recovery.py")
			.codeSnapshot("print('ok')")
			.metadataJson(objectMapper.readTree("{\"toolName\":\"incident_recovery\"}"))
			.displayName("Incident Recovery")
			.displayDescription("Builds recovery guide.")
			.permissionLevel(2)
			.build();
	}

	private ToolPlanRun createBuildRun(TestFixture fixture) {
		return ToolPlanRun.builder()
			.runId(RUN_ID)
			.project(fixture.project())
			.chatSession(fixture.chatSession())
			.requestType(ToolPlanRunRequestType.BUILD_TOOL)
			.requestedByProjectMember(fixture.reviewer())
			.baseToolPlan(fixture.toolPlan())
			.planGroup(fixture.planGroup())
			.build();
	}

	private Tool createBuiltTool(TestFixture fixture) {
		Tool tool = Tool.builder()
			.project(fixture.project())
			.chatSession(fixture.chatSession())
			.createdByProjectMember(fixture.creator())
			.sourceToolPlan(fixture.toolPlan())
			.fileName("incident_recovery.py")
			.status(ToolStatus.APPROVED)
			.build();
		ReflectionTestUtils.setField(tool, "id", 900L);
		return tool;
	}

	private TestFixture createApprovedBuildFixture() {
		User creatorUser = User.builder()
			.employeeNumber("A253001")
			.name("Plan Creator")
			.password("encoded-password")
			.build();
		ReflectionTestUtils.setField(creatorUser, "id", 1L);

		User reviewerUser = User.builder()
			.employeeNumber("A253002")
			.name("Plan Reviewer")
			.password("encoded-password")
			.build();
		ReflectionTestUtils.setField(reviewerUser, "id", 2L);

		Project project = Project.builder()
			.name("Tool Build Project")
			.createdByUser(creatorUser)
			.projectAdminUser(reviewerUser)
			.build();
		ReflectionTestUtils.setField(project, "id", PROJECT_ID);

		ProjectMember creator = ProjectMember.builder()
			.project(project)
			.user(creatorUser)
			.projectRole(ProjectRole.MEMBER)
			.build();
		ReflectionTestUtils.setField(creator, "id", 20L);

		ProjectMember reviewer = ProjectMember.builder()
			.project(project)
			.user(reviewerUser)
			.projectRole(ProjectRole.ADMIN)
			.build();
		ReflectionTestUtils.setField(reviewer, "id", 21L);

		ChatSession chatSession = ChatSession.builder()
			.project(project)
			.projectMember(creator)
			.title("Tool Build Session")
			.build();
		ReflectionTestUtils.setField(chatSession, "id", CHAT_SESSION_ID);

		ToolPlanGroup planGroup = ToolPlanGroup.builder()
			.project(project)
			.chatSession(chatSession)
			.createdByProjectMember(creator)
			.build();
		ReflectionTestUtils.setField(planGroup, "id", 40L);

		ToolPlan toolPlan = ToolPlan.builder()
			.planGroup(planGroup)
			.project(project)
			.chatSession(chatSession)
			.createdByProjectMember(creator)
			.planVersion(1L)
			.rawMarkdown("## approved plan")
			.structuredPlanJson("{\"blocks\":[]}")
			.planSnapshot("{\"source\":\"test\"}")
			.build();
		ReflectionTestUtils.setField(toolPlan, "id", TOOL_PLAN_ID);

		planGroup.markReview(toolPlan);
		toolPlan.requestApproval();
		planGroup.markPending(toolPlan);
		toolPlan.approve();
		planGroup.approve(toolPlan);

		return new TestFixture(project, creator, reviewer, chatSession, planGroup, toolPlan);
	}

	private record TestFixture(
		Project project,
		ProjectMember creator,
		ProjectMember reviewer,
		ChatSession chatSession,
		ToolPlanGroup planGroup,
		ToolPlan toolPlan
	) {
	}
}
