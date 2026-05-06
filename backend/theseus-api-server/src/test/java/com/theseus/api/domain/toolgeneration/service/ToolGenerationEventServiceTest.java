package com.theseus.api.domain.toolgeneration.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatCode;
import static org.mockito.ArgumentMatchers.contains;
import static org.mockito.ArgumentMatchers.same;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.theseus.api.domain.chat.entity.ChatMessageContentType;
import com.theseus.api.domain.chat.entity.ChatMessageType;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.chat.service.ChatMessageService;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolDraftPhase;
import com.theseus.api.domain.tool.entity.ToolStatus;
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.toolgeneration.event.ToolGenerationAssistantMessagePayload;
import com.theseus.api.domain.toolgeneration.event.ToolGenerationDraftPayload;
import com.theseus.api.domain.toolgeneration.event.ToolGenerationEvent;
import com.theseus.api.domain.user.entity.User;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class ToolGenerationEventServiceTest {

	private static final Long PROJECT_ID = 20L;
	private static final Long CHAT_SESSION_ID = 30L;
	private static final Long TOOL_ID = 40L;

	@Mock
	private ToolRepository toolRepository;

	@Mock
	private ChatMessageService chatMessageService;

	private ObjectMapper objectMapper;
	private ToolGenerationEventService toolGenerationEventService;

	@BeforeEach
	void setUp() {
		objectMapper = new ObjectMapper();
		toolGenerationEventService = new ToolGenerationEventService(
			toolRepository,
			chatMessageService,
			objectMapper
		);
	}

	@Test
	@DisplayName("Tool 생성 완료 이벤트를 받으면 ASSISTANT PLAN 메시지를 저장하고 Tool을 REVIEW 단계로 변경한다.")
	void handleCompletedWithDraftResponse() throws Exception {
		// Given
		Tool tool = createTool(ToolDraftPhase.PLAN);
		ToolGenerationEvent event = createCompletedEvent(ChatMessageType.TOOL_DRAFT_RESPONSE);
		when(toolRepository.findByIdAndProjectIdAndChatSessionIdForUpdate(TOOL_ID, PROJECT_ID, CHAT_SESSION_ID))
			.thenReturn(Optional.of(tool));

		// When
		toolGenerationEventService.handleCompleted(event);

		// Then
		assertThat(tool.getDraftPhase()).isEqualTo(ToolDraftPhase.REVIEW);
		assertThat(tool.getRawMarkdown()).isEqualTo("## PLAN v1");
		assertThat(tool.getStructuredPlanJson()).isEqualTo("{\"version\":1,\"blocks\":[]}");
		assertThat(tool.getDraftSnapshot()).isEqualTo("{\"source\":\"core\"}");
		verify(chatMessageService).saveAssistantMessage(
			tool.getChatSession(),
			tool,
			ChatMessageType.TOOL_DRAFT_RESPONSE,
			ChatMessageContentType.MARKDOWN,
			"## PLAN v1"
		);
	}

	@Test
	@DisplayName("Tool 재생성 완료 이벤트를 받으면 ASSISTANT 재생성 메시지를 저장한다.")
	void handleCompletedWithRegenerateResponse() throws Exception {
		// Given
		Tool tool = createTool(ToolDraftPhase.PLAN);
		ToolGenerationEvent event = createCompletedEvent(ChatMessageType.TOOL_REGENERATE_RESPONSE);
		when(toolRepository.findByIdAndProjectIdAndChatSessionIdForUpdate(TOOL_ID, PROJECT_ID, CHAT_SESSION_ID))
			.thenReturn(Optional.of(tool));

		// When
		toolGenerationEventService.handleCompleted(event);

		// Then
		verify(chatMessageService).saveAssistantMessage(
			tool.getChatSession(),
			tool,
			ChatMessageType.TOOL_REGENERATE_RESPONSE,
			ChatMessageContentType.MARKDOWN,
			"## PLAN v1"
		);
	}

	@Test
	@DisplayName("Tool 생성 실패 이벤트를 받으면 SYSTEM_NOTICE를 저장하고 Tool을 PLAN 단계로 유지한다.")
	void handleFailedSavesSystemNotice() {
		// Given
		Tool tool = createTool(ToolDraftPhase.REVIEW);
		ToolGenerationEvent event = createFailedEvent();
		when(toolRepository.findByIdAndProjectIdAndChatSessionIdForUpdate(TOOL_ID, PROJECT_ID, CHAT_SESSION_ID))
			.thenReturn(Optional.of(tool));

		// When
		toolGenerationEventService.handleFailed(event);

		// Then
		assertThat(tool.getDraftPhase()).isEqualTo(ToolDraftPhase.PLAN);
		verify(chatMessageService).saveSystemNoticeMessage(
			same(tool.getChatSession()),
			same(tool),
			contains("AI_GENERATION_FAILED")
		);
	}

	@Test
	@DisplayName("Tool 조회에 실패하면 이벤트를 건너뛰고 메시지를 저장하지 않는다.")
	void skipWhenToolNotFound() throws Exception {
		// Given
		ToolGenerationEvent event = createCompletedEvent(ChatMessageType.TOOL_DRAFT_RESPONSE);
		when(toolRepository.findByIdAndProjectIdAndChatSessionIdForUpdate(TOOL_ID, PROJECT_ID, CHAT_SESSION_ID))
			.thenReturn(Optional.empty());

		// When & Then
		assertThatCode(() -> toolGenerationEventService.handleCompleted(event))
			.doesNotThrowAnyException();
		verifyNoInteractions(chatMessageService);
	}

	private ToolGenerationEvent createCompletedEvent(ChatMessageType messageType) throws Exception {
		return ToolGenerationEvent.builder()
			.eventType("TOOL_GENERATION_COMPLETED")
			.runId("run-1")
			.projectId(PROJECT_ID)
			.chatSessionId(CHAT_SESSION_ID)
			.toolId(TOOL_ID)
			.assistantMessage(ToolGenerationAssistantMessagePayload.builder()
				.messageType(messageType.name())
				.contentType(ChatMessageContentType.MARKDOWN.name())
				.content("## PLAN v1")
				.build())
			.toolDraft(ToolGenerationDraftPayload.builder()
				.rawMarkdown("## PLAN v1")
				.structuredPlanJson(objectMapper.readTree("{\"version\":1,\"blocks\":[]}"))
				.draftSnapshot(objectMapper.readTree("{\"source\":\"core\"}"))
				.build())
			.build();
	}

	private ToolGenerationEvent createFailedEvent() {
		return ToolGenerationEvent.builder()
			.eventType("TOOL_GENERATION_FAILED")
			.runId("run-2")
			.projectId(PROJECT_ID)
			.chatSessionId(CHAT_SESSION_ID)
			.toolId(TOOL_ID)
			.code("AI_GENERATION_FAILED")
			.message("LLM request failed")
			.build();
	}

	private Tool createTool(ToolDraftPhase draftPhase) {
		User user = User.builder()
			.employeeNumber("A186001")
			.name("Tool Event User")
			.password("encoded-password")
			.build();
		ReflectionTestUtils.setField(user, "id", 10L);

		Project project = Project.builder()
			.name("Tool Event Project")
			.createdByUser(user)
			.projectAdminUser(user)
			.build();
		ReflectionTestUtils.setField(project, "id", PROJECT_ID);

		ProjectMember projectMember = ProjectMember.builder()
			.project(project)
			.user(user)
			.projectRole(ProjectRole.MEMBER)
			.build();
		ReflectionTestUtils.setField(projectMember, "id", 21L);

		ChatSession chatSession = ChatSession.builder()
			.project(project)
			.projectMember(projectMember)
			.title("Tool Event Session")
			.build();
		ReflectionTestUtils.setField(chatSession, "id", CHAT_SESSION_ID);

		Tool tool = Tool.builder()
			.project(project)
			.chatSession(chatSession)
			.createdByProjectMember(projectMember)
			.fileName("event-tool")
			.status(ToolStatus.DRAFT)
			.draftPhase(draftPhase)
			.build();
		ReflectionTestUtils.setField(tool, "id", TOOL_ID);
		return tool;
	}
}
