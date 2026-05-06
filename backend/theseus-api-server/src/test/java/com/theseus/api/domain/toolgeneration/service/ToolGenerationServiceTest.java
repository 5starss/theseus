package com.theseus.api.domain.toolgeneration.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.same;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
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
import com.theseus.api.domain.toolgeneration.event.ToolRegenerationRequestEvent;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
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
		assertThat(((ToolGenerationRequestEvent) event.payload()).fileName()).isEqualTo("sales-summary-tool");
	}

	@Test
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
		assertThat(((ToolRegenerationRequestEvent) event.payload()).baseDraftVersion()).isEqualTo(1L);
	}

	private ToolGenerationRequest createGenerationRequest(String fileName, String userMessage) {
		ToolGenerationRequest request = new ToolGenerationRequest();
		ReflectionTestUtils.setField(request, "fileName", fileName);
		ReflectionTestUtils.setField(request, "userMessage", userMessage);
		return request;
	}

	private ToolRegenerationRequest createRegenerationRequest() {
		ToolFeedbackItemRequest feedbackItem = new ToolFeedbackItemRequest();
		ReflectionTestUtils.setField(feedbackItem, "blockId", "input-format");
		ReflectionTestUtils.setField(feedbackItem, "comment", "allow xlsx");

		ToolRegenerationRequest request = new ToolRegenerationRequest();
		ReflectionTestUtils.setField(request, "baseDraftVersion", 1L);
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
		Tool tool = Tool.builder()
			.project(project)
			.chatSession(chatSession)
			.createdByProjectMember(projectMember)
			.fileName("sales-summary-tool")
			.status(status)
			.draftPhase(ToolDraftPhase.REVIEW)
			.build();
		ReflectionTestUtils.setField(tool, "id", id);
		return tool;
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
