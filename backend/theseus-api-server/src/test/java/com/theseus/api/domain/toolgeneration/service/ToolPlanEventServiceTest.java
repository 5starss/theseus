package com.theseus.api.domain.toolgeneration.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.same;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.theseus.api.domain.chat.entity.ChatMessageContentType;
import com.theseus.api.domain.chat.entity.ChatMessageSenderType;
import com.theseus.api.domain.chat.entity.ChatMessageType;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.chat.service.ChatMessageService;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.tool.entity.ToolPlan;
import com.theseus.api.domain.tool.entity.ToolPlanGroup;
import com.theseus.api.domain.tool.entity.ToolPlanRun;
import com.theseus.api.domain.tool.entity.ToolPlanRunRequestType;
import com.theseus.api.domain.tool.entity.ToolPlanRunStatus;
import com.theseus.api.domain.tool.entity.ToolPlanStatus;
import com.theseus.api.domain.tool.repository.ToolPlanGroupRepository;
import com.theseus.api.domain.tool.repository.ToolPlanRepository;
import com.theseus.api.domain.tool.repository.ToolPlanRunRepository;
import com.theseus.api.domain.toolgeneration.event.ToolPlanAssistantMessagePayload;
import com.theseus.api.domain.toolgeneration.event.ToolPlanEvent;
import com.theseus.api.domain.toolgeneration.event.ToolPlanPayload;
import com.theseus.api.domain.user.entity.User;
import java.util.List;
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
class ToolPlanEventServiceTest {

	private static final Long PROJECT_ID = 10L;
	private static final Long CHAT_SESSION_ID = 30L;
	private static final String RUN_ID = "run-250";

	@Mock
	private ToolPlanRunRepository toolPlanRunRepository;

	@Mock
	private ToolPlanGroupRepository toolPlanGroupRepository;

	@Mock
	private ToolPlanRepository toolPlanRepository;

	@Mock
	private ChatMessageService chatMessageService;

	private ObjectMapper objectMapper;
	private ToolPlanEventService toolPlanEventService;

	@BeforeEach
	void setUp() {
		objectMapper = new ObjectMapper();
		toolPlanEventService = new ToolPlanEventService(
			toolPlanRunRepository,
			toolPlanGroupRepository,
			toolPlanRepository,
			chatMessageService,
			objectMapper
		);
	}

	@Test
	@DisplayName("completed 이벤트는 ToolPlanGroup과 ToolPlan v1을 생성하고 Run을 완료한다")
	void handleCompletedCreatesToolPlanGroupAndToolPlan() throws Exception {
		// Given
		TestFixture fixture = createFixture();
		ToolPlanRun toolPlanRun = createRun(fixture, ToolPlanRunRequestType.GENERATE_PLAN, null, null);
		ToolPlanEvent event = createCompletedEvent();
		when(toolPlanRunRepository.findByRunId(RUN_ID)).thenReturn(Optional.of(toolPlanRun));
		when(toolPlanGroupRepository.save(any(ToolPlanGroup.class))).thenAnswer(invocation -> invocation.getArgument(0));
		when(toolPlanRepository.findByPlanGroupOrderByPlanVersionDesc(any(ToolPlanGroup.class))).thenReturn(List.of());
		when(toolPlanRepository.save(any(ToolPlan.class))).thenAnswer(invocation -> {
			ToolPlan savedToolPlan = invocation.getArgument(0);
			ReflectionTestUtils.setField(savedToolPlan, "id", 100L);
			return savedToolPlan;
		});

		// When
		toolPlanEventService.handleCompleted(event);

		// Then
		ArgumentCaptor<ToolPlan> toolPlanCaptor = ArgumentCaptor.forClass(ToolPlan.class);
		verify(toolPlanRepository).save(toolPlanCaptor.capture());
		ToolPlan savedToolPlan = toolPlanCaptor.getValue();
		assertThat(savedToolPlan.getPlanVersion()).isEqualTo(1L);
		assertThat(savedToolPlan.getStatus()).isEqualTo(ToolPlanStatus.REVIEW);
		assertThat(savedToolPlan.getRawMarkdown()).isEqualTo("## PLAN v1");
		assertThat(savedToolPlan.getStructuredPlanJson()).isEqualTo("{\"blocks\":[]}");
		assertThat(savedToolPlan.getPlanSnapshot()).isEqualTo("{\"source\":\"core\"}");
		assertThat(savedToolPlan.getRequestedPrompt()).isEqualTo("장애 로그 분석 Tool을 만들어줘.");

		assertThat(toolPlanRun.getStatus()).isEqualTo(ToolPlanRunStatus.COMPLETED);
		assertThat(toolPlanRun.getResultToolPlan()).isEqualTo(savedToolPlan);
		assertThat(toolPlanRun.getPlanGroup().getLatestToolPlan()).isEqualTo(savedToolPlan);
		assertThat(toolPlanRun.getPlanGroup().getStatus().name()).isEqualTo("REVIEW");
		verify(chatMessageService).saveToolPlanEventMessage(
			same(fixture.chatSession()),
			same(savedToolPlan),
			same(toolPlanRun),
			eq(ChatMessageSenderType.ASSISTANT),
			eq(ChatMessageType.TOOL_PLAN_RESPONSE),
			eq(ChatMessageContentType.MARKDOWN),
			eq("## PLAN v1"),
			eq("tool-plan-event:run-250:TOOL_PLAN_COMPLETED:assistant")
		);
	}

	@Test
	@DisplayName("재생성 completed 이벤트는 같은 group 아래 다음 버전을 만들고 이전 REVIEW PLAN을 대체한다")
	void handleCompletedForRegenerationCreatesNextVersion() throws Exception {
		// Given
		TestFixture fixture = createFixture();
		ToolPlanGroup planGroup = createGroup(fixture);
		ToolPlan previousPlan = createToolPlan(fixture, planGroup, 1L);
		planGroup.markReview(previousPlan);
		ToolPlanRun toolPlanRun = createRun(
			fixture,
			ToolPlanRunRequestType.REGENERATE_PLAN,
			planGroup,
			previousPlan
		);
		ToolPlanEvent event = createCompletedEvent();
		when(toolPlanRunRepository.findByRunId(RUN_ID)).thenReturn(Optional.of(toolPlanRun));
		when(toolPlanRepository.findByPlanGroupOrderByPlanVersionDesc(planGroup)).thenReturn(List.of(previousPlan));
		when(toolPlanRepository.save(any(ToolPlan.class))).thenAnswer(invocation -> invocation.getArgument(0));

		// When
		toolPlanEventService.handleCompleted(event);

		// Then
		ArgumentCaptor<ToolPlan> toolPlanCaptor = ArgumentCaptor.forClass(ToolPlan.class);
		verify(toolPlanRepository).save(toolPlanCaptor.capture());
		ToolPlan savedToolPlan = toolPlanCaptor.getValue();
		assertThat(savedToolPlan.getPlanGroup()).isEqualTo(planGroup);
		assertThat(savedToolPlan.getBaseToolPlan()).isEqualTo(previousPlan);
		assertThat(savedToolPlan.getPlanVersion()).isEqualTo(2L);
		assertThat(previousPlan.getStatus()).isEqualTo(ToolPlanStatus.SUPERSEDED);
		assertThat(planGroup.getLatestToolPlan()).isEqualTo(savedToolPlan);
		assertThat(toolPlanRun.getStatus()).isEqualTo(ToolPlanRunStatus.COMPLETED);
	}

	@Test
	@DisplayName("skipped 이벤트는 Run만 SKIPPED 처리하고 ToolPlan은 만들지 않는다")
	void handleSkippedStoresAssistantChatMessageOnly() {
		// Given
		TestFixture fixture = createFixture();
		ToolPlanRun toolPlanRun = createRun(fixture, ToolPlanRunRequestType.GENERATE_PLAN, null, null);
		ToolPlanEvent event = createSkippedEvent();
		when(toolPlanRunRepository.findByRunId(RUN_ID)).thenReturn(Optional.of(toolPlanRun));

		// When
		toolPlanEventService.handleSkipped(event);

		// Then
		assertThat(toolPlanRun.getStatus()).isEqualTo(ToolPlanRunStatus.SKIPPED);
		assertThat(toolPlanRun.getResultToolPlan()).isNull();
		verifyNoInteractions(toolPlanGroupRepository, toolPlanRepository);
		verify(chatMessageService).saveToolPlanEventMessage(
			same(fixture.chatSession()),
			eq(null),
			same(toolPlanRun),
			eq(ChatMessageSenderType.ASSISTANT),
			eq(ChatMessageType.CHAT),
			eq(ChatMessageContentType.TEXT),
			eq("Tool 명세 생성을 위해 목적과 입출력을 알려주세요."),
			eq("tool-plan-event:run-250:TOOL_PLAN_SKIPPED:assistant")
		);
	}

	@Test
	@DisplayName("failed 이벤트는 Run만 FAILED 처리하고 SYSTEM_NOTICE를 저장한다")
	void handleFailedStoresSystemNoticeOnly() {
		// Given
		TestFixture fixture = createFixture();
		ToolPlanRun toolPlanRun = createRun(fixture, ToolPlanRunRequestType.GENERATE_PLAN, null, null);
		ToolPlanEvent event = createFailedEvent();
		when(toolPlanRunRepository.findByRunId(RUN_ID)).thenReturn(Optional.of(toolPlanRun));

		// When
		toolPlanEventService.handleFailed(event);

		// Then
		assertThat(toolPlanRun.getStatus()).isEqualTo(ToolPlanRunStatus.FAILED);
		assertThat(toolPlanRun.getErrorCode()).isEqualTo("CORE_PLAN_FAILED");
		assertThat(toolPlanRun.getResultToolPlan()).isNull();
		verifyNoInteractions(toolPlanGroupRepository, toolPlanRepository);
		verify(chatMessageService).saveToolPlanEventMessage(
			same(fixture.chatSession()),
			eq(null),
			same(toolPlanRun),
			eq(ChatMessageSenderType.SYSTEM),
			eq(ChatMessageType.SYSTEM_NOTICE),
			eq(ChatMessageContentType.TEXT),
			eq("Tool PLAN 생성에 실패했습니다. code=CORE_PLAN_FAILED, message=PLAN generation failed"),
			eq("tool-plan-event:run-250:TOOL_PLAN_FAILED:system")
		);
	}

	@Test
	@DisplayName("이미 종료된 Run의 terminal 이벤트는 중복 처리하지 않는다")
	void skipAlreadyFinishedRun() throws Exception {
		// Given
		TestFixture fixture = createFixture();
		ToolPlanGroup planGroup = createGroup(fixture);
		ToolPlan resultToolPlan = createToolPlan(fixture, planGroup, 1L);
		ToolPlanRun toolPlanRun = createRun(fixture, ToolPlanRunRequestType.GENERATE_PLAN, null, null);
		toolPlanRun.complete(resultToolPlan, java.time.LocalDateTime.of(2026, 5, 11, 12, 0));
		when(toolPlanRunRepository.findByRunId(RUN_ID)).thenReturn(Optional.of(toolPlanRun));

		// When
		toolPlanEventService.handleCompleted(createCompletedEvent());

		// Then
		verifyNoInteractions(toolPlanGroupRepository, toolPlanRepository, chatMessageService);
	}

	@Test
	@DisplayName("project/session이 맞지 않는 이벤트는 DB 변경 없이 건너뛴다")
	void skipMismatchedProjectOrSession() throws Exception {
		// Given
		TestFixture fixture = createFixture();
		ToolPlanRun toolPlanRun = createRun(fixture, ToolPlanRunRequestType.GENERATE_PLAN, null, null);
		ToolPlanEvent event = ToolPlanEvent.builder()
			.eventType("TOOL_PLAN_COMPLETED")
			.runId(RUN_ID)
			.projectId(999L)
			.chatSessionId(CHAT_SESSION_ID)
			.assistantMessage(createAssistantMessage(ChatMessageType.TOOL_PLAN_RESPONSE, ChatMessageContentType.MARKDOWN))
			.toolPlan(createToolPlanPayload())
			.build();
		when(toolPlanRunRepository.findByRunId(RUN_ID)).thenReturn(Optional.of(toolPlanRun));

		// When
		toolPlanEventService.handleCompleted(event);

		// Then
		assertThat(toolPlanRun.getStatus()).isEqualTo(ToolPlanRunStatus.REQUESTED);
		verifyNoInteractions(toolPlanGroupRepository, toolPlanRepository, chatMessageService);
	}

	private ToolPlanEvent createCompletedEvent() throws Exception {
		return ToolPlanEvent.builder()
			.eventType("TOOL_PLAN_COMPLETED")
			.runId(RUN_ID)
			.eventSequence(1L)
			.projectId(PROJECT_ID)
			.chatSessionId(CHAT_SESSION_ID)
			.assistantMessage(createAssistantMessage(ChatMessageType.TOOL_PLAN_RESPONSE, ChatMessageContentType.MARKDOWN))
			.toolPlan(createToolPlanPayload())
			.completedAt("2026-05-11T12:00:00+09:00")
			.build();
	}

	private ToolPlanEvent createSkippedEvent() {
		return ToolPlanEvent.builder()
			.eventType("TOOL_PLAN_SKIPPED")
			.runId(RUN_ID)
			.eventSequence(2L)
			.projectId(PROJECT_ID)
			.chatSessionId(CHAT_SESSION_ID)
			.assistantMessage(ToolPlanAssistantMessagePayload.builder()
				.messageType(ChatMessageType.CHAT.name())
				.contentType(ChatMessageContentType.TEXT.name())
				.content("Tool 명세 생성을 위해 목적과 입출력을 알려주세요.")
				.build())
			.completedAt("2026-05-11T12:00:00+09:00")
			.build();
	}

	private ToolPlanEvent createFailedEvent() {
		return ToolPlanEvent.builder()
			.eventType("TOOL_PLAN_FAILED")
			.runId(RUN_ID)
			.eventSequence(3L)
			.projectId(PROJECT_ID)
			.chatSessionId(CHAT_SESSION_ID)
			.code("CORE_PLAN_FAILED")
			.message("PLAN generation failed")
			.failedAt("2026-05-11T12:00:00+09:00")
			.build();
	}

	private ToolPlanAssistantMessagePayload createAssistantMessage(
		ChatMessageType messageType,
		ChatMessageContentType contentType
	) {
		return ToolPlanAssistantMessagePayload.builder()
			.messageType(messageType.name())
			.contentType(contentType.name())
			.content("## PLAN v1")
			.build();
	}

	private ToolPlanPayload createToolPlanPayload() throws Exception {
		return ToolPlanPayload.builder()
			.rawMarkdown("## PLAN v1")
			.structuredPlanJson(objectMapper.readTree("{\"blocks\":[]}"))
			.planSnapshot(objectMapper.readTree("{\"source\":\"core\"}"))
			.build();
	}

	private ToolPlanRun createRun(
		TestFixture fixture,
		ToolPlanRunRequestType requestType,
		ToolPlanGroup planGroup,
		ToolPlan baseToolPlan
	) {
		return ToolPlanRun.builder()
			.runId(RUN_ID)
			.project(fixture.project())
			.chatSession(fixture.chatSession())
			.requestType(requestType)
			.requestedByProjectMember(fixture.projectMember())
			.planGroup(planGroup)
			.baseToolPlan(baseToolPlan)
			.requestPayloadJson("{\"prompt\":\"장애 로그 분석 Tool을 만들어줘.\"}")
			.build();
	}

	private ToolPlanGroup createGroup(TestFixture fixture) {
		return ToolPlanGroup.builder()
			.project(fixture.project())
			.chatSession(fixture.chatSession())
			.createdByProjectMember(fixture.projectMember())
			.build();
	}

	private ToolPlan createToolPlan(TestFixture fixture, ToolPlanGroup planGroup, Long planVersion) {
		return ToolPlan.builder()
			.planGroup(planGroup)
			.project(fixture.project())
			.chatSession(fixture.chatSession())
			.createdByProjectMember(fixture.projectMember())
			.planVersion(planVersion)
			.rawMarkdown("raw markdown")
			.structuredPlanJson("{\"blocks\":[]}")
			.planSnapshot("{\"source\":\"test\"}")
			.build();
	}

	private TestFixture createFixture() {
		User user = User.builder()
			.employeeNumber("A250001")
			.name("ToolPlan User")
			.password("encoded-password")
			.build();
		ReflectionTestUtils.setField(user, "id", 1L);

		Project project = Project.builder()
			.name("ToolPlan Project")
			.createdByUser(user)
			.projectAdminUser(user)
			.build();
		ReflectionTestUtils.setField(project, "id", PROJECT_ID);

		ProjectMember projectMember = ProjectMember.builder()
			.project(project)
			.user(user)
			.projectRole(ProjectRole.ADMIN)
			.build();
		ReflectionTestUtils.setField(projectMember, "id", 20L);

		ChatSession chatSession = ChatSession.builder()
			.project(project)
			.projectMember(projectMember)
			.title("ToolPlan Session")
			.build();
		ReflectionTestUtils.setField(chatSession, "id", CHAT_SESSION_ID);

		return new TestFixture(project, projectMember, chatSession);
	}

	private record TestFixture(Project project, ProjectMember projectMember, ChatSession chatSession) {
	}
}
