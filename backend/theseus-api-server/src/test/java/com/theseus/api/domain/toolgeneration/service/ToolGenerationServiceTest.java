package com.theseus.api.domain.toolgeneration.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.same;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.entity.ChatMessageContentType;
import com.theseus.api.domain.chat.entity.ChatMessageType;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.chat.repository.ChatSessionRepository;
import com.theseus.api.domain.chat.service.ChatMessageService;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolDraftPhase;
import com.theseus.api.domain.tool.entity.ToolStatus;
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.toolgeneration.dto.request.ToolFeedbackItemRequest;
import com.theseus.api.domain.toolgeneration.dto.request.ToolGenerationRequest;
import com.theseus.api.domain.toolgeneration.dto.request.ToolRegenerationRequest;
import com.theseus.api.domain.toolgeneration.dto.response.ToolGenerationRunResponse;
import com.theseus.api.domain.toolgeneration.event.ToolGenerationKafkaPublishEvent;
import com.theseus.api.domain.toolgeneration.event.ToolGenerationRequestEvent;
import com.theseus.api.domain.toolgeneration.event.ToolPermissionPayload;
import com.theseus.api.domain.toolgeneration.event.ToolRegenerationRequestEvent;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
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
class ToolGenerationServiceTest {

	@Mock
	private ToolRepository toolRepository;

	@Mock
	private ChatSessionRepository chatSessionRepository;

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

	private ToolGenerationService toolGenerationService;

	@BeforeEach
	void setUp() {
		toolGenerationService = new ToolGenerationService(
			toolRepository,
			chatSessionRepository,
			projectRepository,
			projectMemberRepository,
			userRepository,
			chatMessageService,
			eventPublisher,
			new ObjectMapper()
		);
	}

	@Test
	@DisplayName("Tool 생성 요청은 Draft Tool과 USER 메시지를 저장하고 Core 계약에 맞는 Kafka payload를 발행한다")
	void generateToolCreatesDraftToolAndPublishesKafkaEvent() {
		ProjectFixture fixture = createProjectFixture(true, false);
		ChatSession chatSession = createChatSession(30L, fixture.project(), fixture.projectMember());
		ToolGenerationRequest request = createGenerationRequest("sales-summary-tool", "make a sales summary tool");

		when(userRepository.findById(fixture.user().getId())).thenReturn(Optional.of(fixture.user()));
		when(projectRepository.findById(fixture.project().getId())).thenReturn(Optional.of(fixture.project()));
		when(projectMemberRepository.findByProjectAndUser(fixture.project(), fixture.user()))
			.thenReturn(Optional.of(fixture.projectMember()));
		when(toolRepository.existsByProjectAndFileName(fixture.project(), "sales-summary-tool")).thenReturn(false);
		when(chatSessionRepository.findByIdAndProjectAndProjectMemberForUpdate(
			chatSession.getId(),
			fixture.project(),
			fixture.projectMember()
		)).thenReturn(Optional.of(chatSession));
		when(toolRepository.save(any(Tool.class))).thenAnswer(invocation -> {
			Tool tool = invocation.getArgument(0);
			ReflectionTestUtils.setField(tool, "id", 40L);
			return tool;
		});

		ToolGenerationRunResponse response = toolGenerationService.generateTool(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			chatSession.getId(),
			request
		);

		assertThat(response.getToolId()).isEqualTo(40L);
		assertThat(response.getStatus()).isEqualTo(ToolStatus.DRAFT);
		assertThat(response.getDraftPhase()).isEqualTo(ToolDraftPhase.PLAN);
		assertThat(response.getDraftVersion()).isZero();
		ArgumentCaptor<Tool> toolCaptor = ArgumentCaptor.forClass(Tool.class);
		verify(chatMessageService).saveUserToolMessage(
			same(chatSession),
			toolCaptor.capture(),
			eq(ChatMessageType.TOOL_DRAFT_REQUEST),
			eq(ChatMessageContentType.TEXT),
			eq("make a sales summary tool")
		);
		assertThat(toolCaptor.getValue().getId()).isEqualTo(40L);

		ArgumentCaptor<ToolGenerationKafkaPublishEvent> eventCaptor =
			ArgumentCaptor.forClass(ToolGenerationKafkaPublishEvent.class);
		verify(eventPublisher).publishEvent(eventCaptor.capture());
		ToolGenerationKafkaPublishEvent event = eventCaptor.getValue();
		assertThat(event.regeneration()).isFalse();
		assertThat(event.payload()).isInstanceOf(ToolGenerationRequestEvent.class);
		assertThat(event.key()).isNotBlank();

		ToolGenerationRequestEvent payload = (ToolGenerationRequestEvent) event.payload();
		assertThat(payload.eventType()).isEqualTo("TOOL_GENERATION_REQUESTED");
		assertThat(payload.runId()).isEqualTo(event.key());
		assertThat(payload.projectId()).isEqualTo(fixture.project().getId());
		assertThat(payload.chatSessionId()).isEqualTo(chatSession.getId());
		assertThat(payload.toolId()).isEqualTo(40L);
		assertThat(payload.requestedByUserId()).isEqualTo(fixture.user().getId());
		assertThat(payload.requestedByProjectMemberId()).isEqualTo(fixture.projectMember().getId());
		assertThat(payload.prompt()).isEqualTo("make a sales summary tool");
		assertThat(payload.fileName()).isEqualTo("sales-summary-tool");
		assertThat(payload.projectRole()).isEqualTo(ProjectRole.MEMBER);
		assertThat(payload.requestedAt()).isNotNull();
		assertToolPermissionPayload(payload.toolPermission(), true, true, false, false);
	}

	@Test
	@DisplayName("Tool 재생성 요청은 피드백 메시지를 저장하고 Core 계약에 맞는 Kafka payload를 발행한다")
	void regenerateToolMovesToolToPlanAndPublishesKafkaEvent() {
		ProjectFixture fixture = createProjectFixture(false, false);
		ChatSession chatSession = createChatSession(31L, fixture.project(), fixture.projectMember());
		Tool tool = createTool(41L, fixture.project(), chatSession, fixture.projectMember(), ToolStatus.REJECTED);
		ToolRegenerationRequest request = createRegenerationRequest();

		when(userRepository.findById(fixture.user().getId())).thenReturn(Optional.of(fixture.user()));
		when(projectRepository.findById(fixture.project().getId())).thenReturn(Optional.of(fixture.project()));
		when(projectMemberRepository.findByProjectAndUser(fixture.project(), fixture.user()))
			.thenReturn(Optional.of(fixture.projectMember()));
		when(chatSessionRepository.findByIdAndProjectAndProjectMemberForUpdate(
			chatSession.getId(),
			fixture.project(),
			fixture.projectMember()
		)).thenReturn(Optional.of(chatSession));
		when(toolRepository.findByIdAndProjectAndChatSessionForUpdate(tool.getId(), fixture.project(), chatSession))
			.thenReturn(Optional.of(tool));

		ToolGenerationRunResponse response = toolGenerationService.regenerateTool(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			chatSession.getId(),
			tool.getId(),
			request
		);

		assertThat(response.getToolId()).isEqualTo(tool.getId());
		assertThat(response.getStatus()).isEqualTo(ToolStatus.DRAFT);
		assertThat(response.getDraftPhase()).isEqualTo(ToolDraftPhase.PLAN);
		assertThat(response.getDraftVersion()).isEqualTo(1L);
		assertThat(tool.getDraftVersion()).isEqualTo(1L);
		verify(chatMessageService).saveUserToolMessage(
			chatSession,
			tool,
			ChatMessageType.TOOL_FEEDBACK,
			ChatMessageContentType.JSON,
			"{\"baseDraftVersion\":1,\"feedbackItems\":[{\"blockId\":\"input-format\",\"comment\":\"allow xlsx\"}]}"
		);

		ArgumentCaptor<ToolGenerationKafkaPublishEvent> eventCaptor =
			ArgumentCaptor.forClass(ToolGenerationKafkaPublishEvent.class);
		verify(eventPublisher).publishEvent(eventCaptor.capture());
		ToolGenerationKafkaPublishEvent event = eventCaptor.getValue();
		assertThat(event.regeneration()).isTrue();
		assertThat(event.payload()).isInstanceOf(ToolRegenerationRequestEvent.class);
		assertThat(event.key()).isNotBlank();

		ToolRegenerationRequestEvent payload = (ToolRegenerationRequestEvent) event.payload();
		assertThat(payload.eventType()).isEqualTo("TOOL_REGENERATION_REQUESTED");
		assertThat(payload.runId()).isEqualTo(event.key());
		assertThat(payload.projectId()).isEqualTo(fixture.project().getId());
		assertThat(payload.chatSessionId()).isEqualTo(chatSession.getId());
		assertThat(payload.toolId()).isEqualTo(tool.getId());
		assertThat(payload.requestedByUserId()).isEqualTo(fixture.user().getId());
		assertThat(payload.requestedByProjectMemberId()).isEqualTo(fixture.projectMember().getId());
		assertThat(payload.baseDraftVersion()).isEqualTo(1L);
		assertThat(payload.feedbackItems()).hasSize(1);
		assertThat(payload.feedbackItems().get(0).getBlockId()).isEqualTo("input-format");
		assertThat(payload.feedbackItems().get(0).getComment()).isEqualTo("allow xlsx");
		assertThat(payload.projectRole()).isEqualTo(ProjectRole.MEMBER);
		assertThat(payload.requestedAt()).isNotNull();
		assertToolPermissionPayload(payload.toolPermission(), false, true, false, false);
	}

	@Test
	@DisplayName("baseDraftVersion이 현재 draftVersion과 다르면 부수 효과 없이 재생성을 거부한다")
	void regenerateToolFailsBeforeSideEffectsWhenBaseDraftVersionMismatch() {
		ProjectFixture fixture = createProjectFixture(false, false);
		ChatSession chatSession = createChatSession(32L, fixture.project(), fixture.projectMember());
		Tool tool = createTool(42L, fixture.project(), chatSession, fixture.projectMember(), ToolStatus.REJECTED, 2L);
		ToolRegenerationRequest request = createRegenerationRequest();

		when(userRepository.findById(fixture.user().getId())).thenReturn(Optional.of(fixture.user()));
		when(projectRepository.findById(fixture.project().getId())).thenReturn(Optional.of(fixture.project()));
		when(projectMemberRepository.findByProjectAndUser(fixture.project(), fixture.user()))
			.thenReturn(Optional.of(fixture.projectMember()));
		when(chatSessionRepository.findByIdAndProjectAndProjectMemberForUpdate(
			chatSession.getId(),
			fixture.project(),
			fixture.projectMember()
		)).thenReturn(Optional.of(chatSession));
		when(toolRepository.findByIdAndProjectAndChatSessionForUpdate(tool.getId(), fixture.project(), chatSession))
			.thenReturn(Optional.of(tool));

		assertThatThrownBy(() -> toolGenerationService.regenerateTool(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			chatSession.getId(),
			tool.getId(),
			request
		))
			.isInstanceOfSatisfying(BusinessException.class, exception ->
				assertThat(exception.getErrorCode()).isEqualTo(ErrorCode.TOOL_DRAFT_VERSION_MISMATCH)
			);

		assertThat(tool.getStatus()).isEqualTo(ToolStatus.REJECTED);
		assertThat(tool.getDraftPhase()).isEqualTo(ToolDraftPhase.REVIEW);
		assertThat(tool.getDraftVersion()).isEqualTo(2L);
		verifyNoInteractions(chatMessageService, eventPublisher);
	}

	@Test
	@DisplayName("Tool이 PLAN 단계이면 부수 효과 없이 재생성을 거부한다")
	void regenerateToolFailsBeforeSideEffectsWhenDraftPhaseIsPlan() {
		ProjectFixture fixture = createProjectFixture(false, false);
		ChatSession chatSession = createChatSession(33L, fixture.project(), fixture.projectMember());
		Tool tool = createTool(
			43L,
			fixture.project(),
			chatSession,
			fixture.projectMember(),
			ToolStatus.DRAFT,
			ToolDraftPhase.PLAN,
			0L
		);
		ToolRegenerationRequest request = createRegenerationRequest(0L);

		when(userRepository.findById(fixture.user().getId())).thenReturn(Optional.of(fixture.user()));
		when(projectRepository.findById(fixture.project().getId())).thenReturn(Optional.of(fixture.project()));
		when(projectMemberRepository.findByProjectAndUser(fixture.project(), fixture.user()))
			.thenReturn(Optional.of(fixture.projectMember()));
		when(chatSessionRepository.findByIdAndProjectAndProjectMemberForUpdate(
			chatSession.getId(),
			fixture.project(),
			fixture.projectMember()
		)).thenReturn(Optional.of(chatSession));
		when(toolRepository.findByIdAndProjectAndChatSessionForUpdate(tool.getId(), fixture.project(), chatSession))
			.thenReturn(Optional.of(tool));

		assertThatThrownBy(() -> toolGenerationService.regenerateTool(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			chatSession.getId(),
			tool.getId(),
			request
		))
			.isInstanceOfSatisfying(BusinessException.class, exception ->
				assertThat(exception.getErrorCode()).isEqualTo(ErrorCode.TOOL_DRAFT_REVIEW_PHASE_REQUIRED)
			);

		assertThat(tool.getStatus()).isEqualTo(ToolStatus.DRAFT);
		assertThat(tool.getDraftPhase()).isEqualTo(ToolDraftPhase.PLAN);
		assertThat(tool.getDraftVersion()).isZero();
		verifyNoInteractions(chatMessageService, eventPublisher);
	}

	private ToolGenerationRequest createGenerationRequest(String fileName, String userMessage) {
		ToolGenerationRequest request = new ToolGenerationRequest();
		ReflectionTestUtils.setField(request, "fileName", fileName);
		ReflectionTestUtils.setField(request, "userMessage", userMessage);
		return request;
	}

	private ToolRegenerationRequest createRegenerationRequest() {
		return createRegenerationRequest(1L);
	}

	private ToolRegenerationRequest createRegenerationRequest(Long baseDraftVersion) {
		ToolFeedbackItemRequest feedbackItem = new ToolFeedbackItemRequest();
		ReflectionTestUtils.setField(feedbackItem, "blockId", "input-format");
		ReflectionTestUtils.setField(feedbackItem, "comment", "allow xlsx");

		ToolRegenerationRequest request = new ToolRegenerationRequest();
		ReflectionTestUtils.setField(request, "baseDraftVersion", baseDraftVersion);
		ReflectionTestUtils.setField(request, "feedbackItems", List.of(feedbackItem));
		return request;
	}

	private ProjectFixture createProjectFixture(Boolean canCreateTool, Boolean canUpdateTool) {
		User user = User.builder()
			.employeeNumber("A177001")
			.name("Tool Generation User")
			.password("encoded-password")
			.build();
		ReflectionTestUtils.setField(user, "id", 10L);

		Project project = Project.builder()
			.name("Tool Generation Project")
			.createdByUser(user)
			.projectAdminUser(user)
			.build();
		ReflectionTestUtils.setField(project, "id", 20L);

		ProjectMember projectMember = ProjectMember.builder()
			.project(project)
			.user(user)
			.projectRole(ProjectRole.MEMBER)
			.canCreateTool(canCreateTool)
			.canUpdateTool(canUpdateTool)
			.build();
		ReflectionTestUtils.setField(projectMember, "id", 21L);

		return new ProjectFixture(user, project, projectMember);
	}

	private ChatSession createChatSession(Long id, Project project, ProjectMember projectMember) {
		ChatSession chatSession = ChatSession.builder()
			.project(project)
			.projectMember(projectMember)
			.title("Tool Generation Session")
			.build();
		ReflectionTestUtils.setField(chatSession, "id", id);
		return chatSession;
	}

	private Tool createTool(
		Long id,
		Project project,
		ChatSession chatSession,
		ProjectMember projectMember,
		ToolStatus status
	) {
		return createTool(id, project, chatSession, projectMember, status, 1L);
	}

	private Tool createTool(
		Long id,
		Project project,
		ChatSession chatSession,
		ProjectMember projectMember,
		ToolStatus status,
		Long draftVersion
	) {
		return createTool(id, project, chatSession, projectMember, status, ToolDraftPhase.REVIEW, draftVersion);
	}

	private Tool createTool(
		Long id,
		Project project,
		ChatSession chatSession,
		ProjectMember projectMember,
		ToolStatus status,
		ToolDraftPhase draftPhase,
		Long draftVersion
	) {
		Tool tool = Tool.builder()
			.project(project)
			.chatSession(chatSession)
			.createdByProjectMember(projectMember)
			.fileName("sales-summary-tool")
			.status(status)
			.draftPhase(draftPhase)
			.draftVersion(draftVersion)
			.build();
		ReflectionTestUtils.setField(tool, "id", id);
		return tool;
	}

	private void assertToolPermissionPayload(
		ToolPermissionPayload payload,
		Boolean canCreateTool,
		Boolean canUseTool,
		Boolean canUpdateTool,
		Boolean canDeleteTool
	) {
		assertThat(payload.canCreateTool()).isEqualTo(canCreateTool);
		assertThat(payload.canUseTool()).isEqualTo(canUseTool);
		assertThat(payload.canUpdateTool()).isEqualTo(canUpdateTool);
		assertThat(payload.canDeleteTool()).isEqualTo(canDeleteTool);
	}

	private AuthenticatedUser createAuthenticatedUser(User user) {
		return new AuthenticatedUser(
			user.getId(),
			user.getEmployeeNumber(),
			user.getName(),
			user.getSystemRole()
		);
	}

	private record ProjectFixture(
		User user,
		Project project,
		ProjectMember projectMember
	) {
	}
}
