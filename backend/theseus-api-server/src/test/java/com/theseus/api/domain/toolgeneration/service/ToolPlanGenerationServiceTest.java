package com.theseus.api.domain.toolgeneration.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.same;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.entity.ChatMessage;
import com.theseus.api.domain.chat.entity.ChatMessageContentType;
import com.theseus.api.domain.chat.entity.ChatMessageSenderType;
import com.theseus.api.domain.chat.entity.ChatMessageType;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.chat.repository.ChatMessageRepository;
import com.theseus.api.domain.chat.repository.ChatSessionRepository;
import com.theseus.api.domain.chat.service.ChatMessageService;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.tool.entity.ToolPlan;
import com.theseus.api.domain.tool.entity.ToolPlanGroup;
import com.theseus.api.domain.tool.entity.ToolPlanMode;
import com.theseus.api.domain.tool.entity.ToolPlanRun;
import com.theseus.api.domain.tool.entity.ToolPlanRunRequestType;
import com.theseus.api.domain.tool.entity.ToolPlanRunStatus;
import com.theseus.api.domain.tool.entity.ToolPlanStatus;
import com.theseus.api.domain.tool.repository.ToolPlanRepository;
import com.theseus.api.domain.tool.repository.ToolPlanRunRepository;
import com.theseus.api.domain.toolgeneration.dto.request.ToolFeedbackItemRequest;
import com.theseus.api.domain.toolgeneration.dto.request.ToolPlanGenerationRequest;
import com.theseus.api.domain.toolgeneration.dto.request.ToolPlanRegenerationRequest;
import com.theseus.api.domain.toolgeneration.dto.response.ToolPlanGenerationRunResponse;
import com.theseus.api.domain.toolgeneration.event.ToolPlanGenerationRequestEvent;
import com.theseus.api.domain.toolgeneration.event.ToolPlanKafkaPublishEvent;
import com.theseus.api.domain.toolgeneration.event.ToolPlanRegenerationRequestEvent;
import com.theseus.api.domain.user.entity.SystemRole;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.time.LocalDateTime;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class ToolPlanGenerationServiceTest {

	@Mock
	private ToolPlanRunRepository toolPlanRunRepository;

	@Mock
	private ToolPlanRepository toolPlanRepository;

	@Mock
	private ChatSessionRepository chatSessionRepository;

	@Mock
	private ChatMessageRepository chatMessageRepository;

	@Mock
	private ProjectRepository projectRepository;

	@Mock
	private ProjectMemberRepository projectMemberRepository;

	@Mock
	private UserRepository userRepository;

	@Mock
	private ChatMessageService chatMessageService;

	@Mock
	private ApplicationEventPublisher eventPublisher;

	private ToolPlanGenerationService toolPlanGenerationService;

	@BeforeEach
	void setUp() {
		ObjectMapper objectMapper = new ObjectMapper();
		objectMapper.registerModule(new JavaTimeModule());
		toolPlanGenerationService = new ToolPlanGenerationService(
			toolPlanRunRepository,
			toolPlanRepository,
			chatSessionRepository,
			chatMessageRepository,
			projectRepository,
			projectMemberRepository,
			userRepository,
			chatMessageService,
			eventPublisher,
			objectMapper
		);
	}

	@Test
	@DisplayName("PLAN 생성 요청은 ToolPlanRun과 USER 메시지를 저장하고 Kafka 이벤트를 발행한다")
	void generatePlanCreatesToolPlanRunAndPublishesKafkaEvent() {
		ProjectFixture fixture = createProjectFixture(true, ProjectMemberStatus.IN_PROGRESS);
		ChatSession chatSession = createChatSession(30L, fixture.project(), fixture.projectMember(), false);
		ToolPlanGenerationRequest request = createRequest(ToolPlanMode.PLAN, "장애 로그 분석 Tool PLAN을 만들어줘.");
		List<ChatMessage> history = List.of(
			createChatMessage(chatSession, 1, ChatMessageSenderType.USER, "이전 질문"),
			createChatMessage(chatSession, 2, ChatMessageSenderType.ASSISTANT, "이전 답변")
		);
		ChatMessage savedUserMessage = createChatMessage(
			chatSession,
			3,
			ChatMessageSenderType.USER,
			request.getPrompt()
		);
		ReflectionTestUtils.setField(savedUserMessage, "id", 400L);

		when(userRepository.findById(fixture.user().getId())).thenReturn(Optional.of(fixture.user()));
		when(projectRepository.findById(fixture.project().getId())).thenReturn(Optional.of(fixture.project()));
		when(projectMemberRepository.findByProjectAndUser(fixture.project(), fixture.user()))
			.thenReturn(Optional.of(fixture.projectMember()));
		when(chatSessionRepository.findByIdAndProjectAndProjectMemberForUpdate(
			chatSession.getId(),
			fixture.project(),
			fixture.projectMember()
		)).thenReturn(Optional.of(chatSession));
		when(chatMessageRepository.findByChatSessionOrderByMessageOrderAsc(chatSession)).thenReturn(history);
		when(toolPlanRunRepository.save(any(ToolPlanRun.class))).thenAnswer(invocation -> invocation.getArgument(0));
		when(chatMessageService.saveUserToolPlanRunMessage(
			same(chatSession),
			any(ToolPlanRun.class),
			eq(ChatMessageType.TOOL_PLAN_REQUEST),
			eq(ChatMessageContentType.TEXT),
			eq(request.getPrompt())
		)).thenReturn(savedUserMessage);

		ToolPlanGenerationRunResponse response = toolPlanGenerationService.generatePlan(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			chatSession.getId(),
			request
		);

		assertThat(response.getRunId()).isNotBlank();
		assertThat(response.getProjectId()).isEqualTo(fixture.project().getId());
		assertThat(response.getSessionId()).isEqualTo(chatSession.getId());
		assertThat(response.getStatus()).isEqualTo(ToolPlanRunStatus.REQUESTED);
		assertThat(response.getSseUrl())
			.isEqualTo("/api/v1/projects/10/sessions/30/tool-plan-runs/" + response.getRunId() + "/events");

		ArgumentCaptor<ToolPlanRun> runCaptor = ArgumentCaptor.forClass(ToolPlanRun.class);
		verify(toolPlanRunRepository).save(runCaptor.capture());
		ToolPlanRun savedRun = runCaptor.getValue();
		assertThat(savedRun.getRequestType()).isEqualTo(ToolPlanRunRequestType.GENERATE_PLAN);
		assertThat(savedRun.getMode()).isEqualTo(ToolPlanMode.PLAN);
		assertThat(savedRun.getStatus()).isEqualTo(ToolPlanRunStatus.REQUESTED);
		assertThat(savedRun.getUserMessageId()).isEqualTo(400L);
		assertThat(savedRun.getHistorySnapshotJson()).contains("이전 질문").doesNotContain(request.getPrompt());
		assertThat(savedRun.getRequestPayloadJson()).contains("TOOL_PLAN_REQUESTED").contains(request.getPrompt());

		ArgumentCaptor<ToolPlanKafkaPublishEvent> eventCaptor =
			ArgumentCaptor.forClass(ToolPlanKafkaPublishEvent.class);
		verify(eventPublisher).publishEvent(eventCaptor.capture());
		ToolPlanKafkaPublishEvent event = eventCaptor.getValue();
		assertThat(event.key()).isEqualTo(response.getRunId());
		assertThat(event.payload()).isInstanceOf(ToolPlanGenerationRequestEvent.class);

		ToolPlanGenerationRequestEvent payload = (ToolPlanGenerationRequestEvent) event.payload();
		assertThat(payload.eventType()).isEqualTo("TOOL_PLAN_REQUESTED");
		assertThat(payload.mode()).isEqualTo(ToolPlanMode.PLAN);
		assertThat(payload.runId()).isEqualTo(response.getRunId());
		assertThat(payload.projectId()).isEqualTo(fixture.project().getId());
		assertThat(payload.chatSessionId()).isEqualTo(chatSession.getId());
		assertThat(payload.requestedByUserId()).isEqualTo(fixture.user().getId());
		assertThat(payload.requestedByProjectMemberId()).isEqualTo(fixture.projectMember().getId());
		assertThat(payload.prompt()).isEqualTo(request.getPrompt());
		assertThat(payload.history()).hasSize(2);
		assertThat(payload.history().get(0).content()).isEqualTo("이전 질문");
		assertThat(payload.requestedAt()).isNotNull();
	}

	@Test
	@DisplayName("PLAN 모드가 아니면 PLAN 생성 요청을 거부한다")
	void generatePlanFailsWhenModeIsNotPlan() {
		ToolPlanGenerationRequest request = createRequest(ToolPlanMode.ASK, "그냥 질문");

		assertThatThrownBy(() -> toolPlanGenerationService.generatePlan(
			new AuthenticatedUser(1L, "A001", "테스트", SystemRole.USER),
			10L,
			30L,
			request
		))
			.isInstanceOfSatisfying(BusinessException.class, exception ->
				assertThat(exception.getErrorCode()).isEqualTo(ErrorCode.TOOL_PLAN_REQUEST_MODE_INVALID)
			);

		verifyNoInteractions(userRepository, toolPlanRunRepository, chatMessageService, eventPublisher);
	}

	@Test
	@DisplayName("Tool 생성 권한이 없으면 PLAN 생성 요청을 거부한다")
	void generatePlanFailsWhenProjectMemberCannotCreateTool() {
		ProjectFixture fixture = createProjectFixture(false, ProjectMemberStatus.IN_PROGRESS);
		ToolPlanGenerationRequest request = createRequest(ToolPlanMode.PLAN, "PLAN 생성");

		when(userRepository.findById(fixture.user().getId())).thenReturn(Optional.of(fixture.user()));
		when(projectRepository.findById(fixture.project().getId())).thenReturn(Optional.of(fixture.project()));
		when(projectMemberRepository.findByProjectAndUser(fixture.project(), fixture.user()))
			.thenReturn(Optional.of(fixture.projectMember()));

		assertThatThrownBy(() -> toolPlanGenerationService.generatePlan(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			30L,
			request
		))
			.isInstanceOfSatisfying(BusinessException.class, exception ->
				assertThat(exception.getErrorCode()).isEqualTo(ErrorCode.TOOL_CREATE_PERMISSION_REQUIRED)
			);

		verify(toolPlanRunRepository, never()).save(any());
		verifyNoInteractions(chatMessageService, eventPublisher);
	}

	@Test
	@DisplayName("종료된 ChatSession에는 PLAN 생성 요청을 등록할 수 없다")
	void generatePlanFailsWhenChatSessionIsClosed() {
		ProjectFixture fixture = createProjectFixture(true, ProjectMemberStatus.IN_PROGRESS);
		ChatSession chatSession = createChatSession(30L, fixture.project(), fixture.projectMember(), true);
		ToolPlanGenerationRequest request = createRequest(ToolPlanMode.PLAN, "PLAN 생성");

		when(userRepository.findById(fixture.user().getId())).thenReturn(Optional.of(fixture.user()));
		when(projectRepository.findById(fixture.project().getId())).thenReturn(Optional.of(fixture.project()));
		when(projectMemberRepository.findByProjectAndUser(fixture.project(), fixture.user()))
			.thenReturn(Optional.of(fixture.projectMember()));
		when(chatSessionRepository.findByIdAndProjectAndProjectMemberForUpdate(
			chatSession.getId(),
			fixture.project(),
			fixture.projectMember()
		)).thenReturn(Optional.of(chatSession));

		assertThatThrownBy(() -> toolPlanGenerationService.generatePlan(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			chatSession.getId(),
			request
		))
			.isInstanceOfSatisfying(BusinessException.class, exception ->
				assertThat(exception.getErrorCode()).isEqualTo(ErrorCode.CLOSED_CHAT_SESSION)
			);

		verify(toolPlanRunRepository, never()).save(any());
		verifyNoInteractions(chatMessageService, eventPublisher);
	}

	@Test
	@DisplayName("ToolPlan 재생성 요청은 feedback 메시지와 REGENERATE_PLAN run을 저장하고 Kafka 이벤트를 발행한다")
	void regeneratePlanCreatesToolPlanRunAndPublishesKafkaEvent() {
		ProjectFixture fixture = createProjectFixture(true, ProjectMemberStatus.IN_PROGRESS);
		ChatSession chatSession = createChatSession(30L, fixture.project(), fixture.projectMember(), false);
		ToolPlanGroup planGroup = createToolPlanGroup(40L, fixture, chatSession);
		ToolPlan baseToolPlan = createToolPlan(50L, fixture, chatSession, planGroup, 2L, ToolPlanStatus.REVIEW);
		ToolPlanRegenerationRequest request = createRegenerationRequest(ToolPlanMode.PLAN, 2L);
		ChatMessage savedUserMessage = createChatMessage(
			chatSession,
			4,
			ChatMessageSenderType.USER,
			"{\"feedbackItems\":[]}"
		);
		ReflectionTestUtils.setField(savedUserMessage, "id", 401L);
		List<ChatMessage> history = List.of(
			createChatMessage(chatSession, 1, ChatMessageSenderType.USER, "이전 질문"),
			createChatMessage(chatSession, 2, ChatMessageSenderType.ASSISTANT, "PLAN v1"),
			savedUserMessage
		);

		when(userRepository.findById(fixture.user().getId())).thenReturn(Optional.of(fixture.user()));
		when(projectRepository.findById(fixture.project().getId())).thenReturn(Optional.of(fixture.project()));
		when(projectMemberRepository.findByProjectAndUser(fixture.project(), fixture.user()))
			.thenReturn(Optional.of(fixture.projectMember()));
		when(chatSessionRepository.findByIdAndProjectAndProjectMemberForUpdate(
			chatSession.getId(),
			fixture.project(),
			fixture.projectMember()
		)).thenReturn(Optional.of(chatSession));
		when(toolPlanRepository.findByIdAndProjectAndChatSessionForUpdate(
			baseToolPlan.getId(),
			fixture.project(),
			chatSession
		)).thenReturn(Optional.of(baseToolPlan));
		when(toolPlanRunRepository.save(any(ToolPlanRun.class))).thenAnswer(invocation -> invocation.getArgument(0));
		when(chatMessageService.saveUserToolPlanMessage(
			same(chatSession),
			same(baseToolPlan),
			any(ToolPlanRun.class),
			eq(ChatMessageType.TOOL_FEEDBACK),
			eq(ChatMessageContentType.JSON),
			any(String.class)
		)).thenReturn(savedUserMessage);
		when(chatMessageRepository.findByChatSessionOrderByMessageOrderAsc(chatSession)).thenReturn(history);

		ToolPlanGenerationRunResponse response = toolPlanGenerationService.regeneratePlan(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			chatSession.getId(),
			baseToolPlan.getId(),
			request
		);

		assertThat(response.getRunId()).isNotBlank();
		assertThat(response.getStatus()).isEqualTo(ToolPlanRunStatus.REQUESTED);
		assertThat(response.getSseUrl())
			.isEqualTo("/api/v1/projects/10/sessions/30/tool-plan-runs/" + response.getRunId() + "/events");

		ArgumentCaptor<ToolPlanRun> runCaptor = ArgumentCaptor.forClass(ToolPlanRun.class);
		verify(toolPlanRunRepository).save(runCaptor.capture());
		ToolPlanRun savedRun = runCaptor.getValue();
		assertThat(savedRun.getRequestType()).isEqualTo(ToolPlanRunRequestType.REGENERATE_PLAN);
		assertThat(savedRun.getBaseToolPlan()).isEqualTo(baseToolPlan);
		assertThat(savedRun.getPlanGroup()).isEqualTo(planGroup);
		assertThat(savedRun.getUserMessageId()).isEqualTo(401L);
		assertThat(savedRun.getRequestPayloadJson()).contains("TOOL_PLAN_REGENERATION_REQUESTED");
		assertThat(savedRun.getHistorySnapshotJson()).contains("PLAN v1");

		ArgumentCaptor<ToolPlanKafkaPublishEvent> eventCaptor =
			ArgumentCaptor.forClass(ToolPlanKafkaPublishEvent.class);
		verify(eventPublisher).publishEvent(eventCaptor.capture());
		ToolPlanKafkaPublishEvent event = eventCaptor.getValue();
		assertThat(event.key()).isEqualTo(response.getRunId());
		assertThat(event.payload()).isInstanceOf(ToolPlanRegenerationRequestEvent.class);

		ToolPlanRegenerationRequestEvent payload = (ToolPlanRegenerationRequestEvent) event.payload();
		assertThat(payload.eventType()).isEqualTo("TOOL_PLAN_REGENERATION_REQUESTED");
		assertThat(payload.mode()).isEqualTo(ToolPlanMode.PLAN);
		assertThat(payload.runId()).isEqualTo(response.getRunId());
		assertThat(payload.projectId()).isEqualTo(fixture.project().getId());
		assertThat(payload.chatSessionId()).isEqualTo(chatSession.getId());
		assertThat(payload.baseToolPlanId()).isEqualTo(baseToolPlan.getId());
		assertThat(payload.planGroupId()).isEqualTo(planGroup.getId());
		assertThat(payload.basePlanVersion()).isEqualTo(2L);
		assertThat(payload.basePlan().rawMarkdown()).isEqualTo("raw markdown v2");
		assertThat(payload.basePlan().structuredPlanJson().get("blocks")).isNotNull();
		assertThat(payload.feedbackItems()).hasSize(1);
		assertThat(payload.feedbackItems().get(0).getBlockId()).isEqualTo("analysis-summary");
		assertThat(payload.history()).hasSize(3);
		verify(toolPlanRepository, never()).save(any());
	}

	@Test
	@DisplayName("REJECTED 상태의 ToolPlan도 재생성 요청을 받을 수 있다")
	void regeneratePlanAllowsRejectedBaseToolPlan() {
		ProjectFixture fixture = createProjectFixture(true, ProjectMemberStatus.IN_PROGRESS);
		ChatSession chatSession = createChatSession(30L, fixture.project(), fixture.projectMember(), false);
		ToolPlanGroup planGroup = createToolPlanGroup(40L, fixture, chatSession);
		ToolPlan baseToolPlan = createToolPlan(50L, fixture, chatSession, planGroup, 1L, ToolPlanStatus.REJECTED);
		ToolPlanRegenerationRequest request = createRegenerationRequest(ToolPlanMode.PLAN, 1L);
		ChatMessage savedUserMessage = createChatMessage(chatSession, 3, ChatMessageSenderType.USER, "{}");
		ReflectionTestUtils.setField(savedUserMessage, "id", 401L);

		when(userRepository.findById(fixture.user().getId())).thenReturn(Optional.of(fixture.user()));
		when(projectRepository.findById(fixture.project().getId())).thenReturn(Optional.of(fixture.project()));
		when(projectMemberRepository.findByProjectAndUser(fixture.project(), fixture.user()))
			.thenReturn(Optional.of(fixture.projectMember()));
		when(chatSessionRepository.findByIdAndProjectAndProjectMemberForUpdate(
			chatSession.getId(),
			fixture.project(),
			fixture.projectMember()
		)).thenReturn(Optional.of(chatSession));
		when(toolPlanRepository.findByIdAndProjectAndChatSessionForUpdate(
			baseToolPlan.getId(),
			fixture.project(),
			chatSession
		)).thenReturn(Optional.of(baseToolPlan));
		when(toolPlanRunRepository.save(any(ToolPlanRun.class))).thenAnswer(invocation -> invocation.getArgument(0));
		when(chatMessageService.saveUserToolPlanMessage(
			same(chatSession),
			same(baseToolPlan),
			any(ToolPlanRun.class),
			eq(ChatMessageType.TOOL_FEEDBACK),
			eq(ChatMessageContentType.JSON),
			any(String.class)
		)).thenReturn(savedUserMessage);
		when(chatMessageRepository.findByChatSessionOrderByMessageOrderAsc(chatSession)).thenReturn(List.of(savedUserMessage));

		ToolPlanGenerationRunResponse response = toolPlanGenerationService.regeneratePlan(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			chatSession.getId(),
			baseToolPlan.getId(),
			request
		);

		assertThat(response.getStatus()).isEqualTo(ToolPlanRunStatus.REQUESTED);
		verify(eventPublisher).publishEvent(any(ToolPlanKafkaPublishEvent.class));
	}

	@Test
	@DisplayName("REVIEW/REJECTED가 아닌 ToolPlan은 재생성할 수 없다")
	void regeneratePlanFailsWhenBaseToolPlanStatusIsNotRegeneratable() {
		ProjectFixture fixture = createProjectFixture(true, ProjectMemberStatus.IN_PROGRESS);
		ChatSession chatSession = createChatSession(30L, fixture.project(), fixture.projectMember(), false);
		ToolPlanGroup planGroup = createToolPlanGroup(40L, fixture, chatSession);
		ToolPlan baseToolPlan = createToolPlan(50L, fixture, chatSession, planGroup, 1L, ToolPlanStatus.PENDING);
		ToolPlanRegenerationRequest request = createRegenerationRequest(ToolPlanMode.PLAN, 1L);

		when(userRepository.findById(fixture.user().getId())).thenReturn(Optional.of(fixture.user()));
		when(projectRepository.findById(fixture.project().getId())).thenReturn(Optional.of(fixture.project()));
		when(projectMemberRepository.findByProjectAndUser(fixture.project(), fixture.user()))
			.thenReturn(Optional.of(fixture.projectMember()));
		when(chatSessionRepository.findByIdAndProjectAndProjectMemberForUpdate(
			chatSession.getId(),
			fixture.project(),
			fixture.projectMember()
		)).thenReturn(Optional.of(chatSession));
		when(toolPlanRepository.findByIdAndProjectAndChatSessionForUpdate(
			baseToolPlan.getId(),
			fixture.project(),
			chatSession
		)).thenReturn(Optional.of(baseToolPlan));

		assertThatThrownBy(() -> toolPlanGenerationService.regeneratePlan(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			chatSession.getId(),
			baseToolPlan.getId(),
			request
		))
			.isInstanceOfSatisfying(BusinessException.class, exception ->
				assertThat(exception.getErrorCode()).isEqualTo(ErrorCode.TOOL_PLAN_REGENERATION_STATUS_REQUIRED)
			);

		verify(toolPlanRunRepository, never()).save(any());
		verifyNoInteractions(chatMessageService, eventPublisher);
	}

	@Test
	@DisplayName("basePlanVersion이 현재 ToolPlan 버전과 다르면 재생성 요청을 거부한다")
	void regeneratePlanFailsWhenBasePlanVersionMismatches() {
		ProjectFixture fixture = createProjectFixture(true, ProjectMemberStatus.IN_PROGRESS);
		ChatSession chatSession = createChatSession(30L, fixture.project(), fixture.projectMember(), false);
		ToolPlanGroup planGroup = createToolPlanGroup(40L, fixture, chatSession);
		ToolPlan baseToolPlan = createToolPlan(50L, fixture, chatSession, planGroup, 2L, ToolPlanStatus.REVIEW);
		ToolPlanRegenerationRequest request = createRegenerationRequest(ToolPlanMode.PLAN, 1L);

		when(userRepository.findById(fixture.user().getId())).thenReturn(Optional.of(fixture.user()));
		when(projectRepository.findById(fixture.project().getId())).thenReturn(Optional.of(fixture.project()));
		when(projectMemberRepository.findByProjectAndUser(fixture.project(), fixture.user()))
			.thenReturn(Optional.of(fixture.projectMember()));
		when(chatSessionRepository.findByIdAndProjectAndProjectMemberForUpdate(
			chatSession.getId(),
			fixture.project(),
			fixture.projectMember()
		)).thenReturn(Optional.of(chatSession));
		when(toolPlanRepository.findByIdAndProjectAndChatSessionForUpdate(
			baseToolPlan.getId(),
			fixture.project(),
			chatSession
		)).thenReturn(Optional.of(baseToolPlan));

		assertThatThrownBy(() -> toolPlanGenerationService.regeneratePlan(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			chatSession.getId(),
			baseToolPlan.getId(),
			request
		))
			.isInstanceOfSatisfying(BusinessException.class, exception ->
				assertThat(exception.getErrorCode()).isEqualTo(ErrorCode.TOOL_PLAN_VERSION_MISMATCH)
			);

		verify(toolPlanRunRepository, never()).save(any());
		verifyNoInteractions(chatMessageService, eventPublisher);
	}

	@Test
	@DisplayName("Kafka 諛쒗뻾 ?ㅽ뙣瑜??섏떊?섎㈃ ToolPlanRun??FAILED濡??꾪솚?쒕떎")
	void markRunPublishFailedChangesRunStatusToFailed() {
		ProjectFixture fixture = createProjectFixture(true, ProjectMemberStatus.IN_PROGRESS);
		ChatSession chatSession = createChatSession(30L, fixture.project(), fixture.projectMember(), false);
		ToolPlanRun toolPlanRun = ToolPlanRun.builder()
			.runId("run-failed")
			.project(fixture.project())
			.chatSession(chatSession)
			.requestType(ToolPlanRunRequestType.GENERATE_PLAN)
			.requestedByProjectMember(fixture.projectMember())
			.build();
		when(toolPlanRunRepository.findByRunId("run-failed")).thenReturn(Optional.of(toolPlanRun));

		toolPlanGenerationService.markRunPublishFailed(
			"run-failed",
			new IllegalStateException("kafka send failed")
		);

		assertThat(toolPlanRun.getStatus()).isEqualTo(ToolPlanRunStatus.FAILED);
		assertThat(toolPlanRun.getErrorCode()).isEqualTo(ErrorCode.TOOL_PLAN_KAFKA_PUBLISH_FAILED.getCode());
		assertThat(toolPlanRun.getErrorMessage()).isEqualTo("kafka send failed");
		assertThat(toolPlanRun.getCompletedAt()).isNotNull();
	}

	private ToolPlanGenerationRequest createRequest(ToolPlanMode mode, String prompt) {
		ToolPlanGenerationRequest request = new ToolPlanGenerationRequest();
		ReflectionTestUtils.setField(request, "mode", mode);
		ReflectionTestUtils.setField(request, "prompt", prompt);
		return request;
	}

	private ToolPlanRegenerationRequest createRegenerationRequest(ToolPlanMode mode, Long basePlanVersion) {
		ToolFeedbackItemRequest feedbackItem = new ToolFeedbackItemRequest();
		ReflectionTestUtils.setField(feedbackItem, "blockId", "analysis-summary");
		ReflectionTestUtils.setField(feedbackItem, "comment", "장애 원인 분석을 더 구체적으로 작성해줘.");

		ToolPlanRegenerationRequest request = new ToolPlanRegenerationRequest();
		ReflectionTestUtils.setField(request, "mode", mode);
		ReflectionTestUtils.setField(request, "basePlanVersion", basePlanVersion);
		ReflectionTestUtils.setField(request, "feedbackItems", List.of(feedbackItem));
		return request;
	}

	private ToolPlanGroup createToolPlanGroup(
		Long id,
		ProjectFixture fixture,
		ChatSession chatSession
	) {
		ToolPlanGroup planGroup = ToolPlanGroup.builder()
			.project(fixture.project())
			.chatSession(chatSession)
			.createdByProjectMember(fixture.projectMember())
			.build();
		ReflectionTestUtils.setField(planGroup, "id", id);
		return planGroup;
	}

	private ToolPlan createToolPlan(
		Long id,
		ProjectFixture fixture,
		ChatSession chatSession,
		ToolPlanGroup planGroup,
		Long planVersion,
		ToolPlanStatus status
	) {
		ToolPlan toolPlan = ToolPlan.builder()
			.planGroup(planGroup)
			.project(fixture.project())
			.chatSession(chatSession)
			.createdByProjectMember(fixture.projectMember())
			.planVersion(planVersion)
			.status(status)
			.rawMarkdown("raw markdown v" + planVersion)
			.structuredPlanJson("{\"blocks\":[{\"blockId\":\"analysis-summary\",\"title\":\"분석 요약\",\"content\":\"내용\"}]}")
			.planSnapshot("{\"planVersion\":" + planVersion + "}")
			.build();
		ReflectionTestUtils.setField(toolPlan, "id", id);
		return toolPlan;
	}

	private ChatMessage createChatMessage(
		ChatSession chatSession,
		Integer messageOrder,
		ChatMessageSenderType senderType,
		String content
	) {
		return ChatMessage.builder()
			.chatSession(chatSession)
			.messageOrder(messageOrder)
			.senderType(senderType)
			.messageType(ChatMessageType.CHAT)
			.contentType(ChatMessageContentType.TEXT)
			.content(content)
			.build();
	}

	private ProjectFixture createProjectFixture(boolean canCreateTool, ProjectMemberStatus status) {
		User user = User.builder()
			.employeeNumber("A001")
			.name("테스트 사용자")
			.password("encoded-password")
			.systemRole(SystemRole.USER)
			.build();
		ReflectionTestUtils.setField(user, "id", 1L);

		Project project = Project.builder()
			.name("테스트 프로젝트")
			.createdByUser(user)
			.projectAdminUser(user)
			.build();
		ReflectionTestUtils.setField(project, "id", 10L);

		ProjectMember projectMember = ProjectMember.builder()
			.project(project)
			.user(user)
			.projectRole(ProjectRole.ADMIN)
			.canCreateTool(canCreateTool)
			.canUseTool(true)
			.status(status)
			.build();
		ReflectionTestUtils.setField(projectMember, "id", 20L);

		return new ProjectFixture(user, project, projectMember);
	}

	private ChatSession createChatSession(
		Long id,
		Project project,
		ProjectMember projectMember,
		boolean isClosed
	) {
		ChatSession chatSession = ChatSession.builder()
			.project(project)
			.projectMember(projectMember)
			.title("테스트 세션")
			.build();
		ReflectionTestUtils.setField(chatSession, "id", id);
		if (isClosed) {
			chatSession.close(LocalDateTime.of(2026, 5, 11, 10, 0));
		}
		return chatSession;
	}

	private AuthenticatedUser createAuthenticatedUser(User user) {
		return new AuthenticatedUser(user.getId(), user.getEmployeeNumber(), user.getName(), user.getSystemRole());
	}

	private record ProjectFixture(User user, Project project, ProjectMember projectMember) {
	}
}
