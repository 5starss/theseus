package com.theseus.api.domain.toolgeneration.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.same;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.tool.entity.ToolPlanRun;
import com.theseus.api.domain.tool.entity.ToolPlanRunRequestType;
import com.theseus.api.domain.toolgeneration.config.ToolGenerationStateProperties;
import com.theseus.api.domain.toolgeneration.dto.ToolPlanRunSseEvent;
import com.theseus.api.domain.toolgeneration.dto.ToolPlanRunState;
import com.theseus.api.domain.toolgeneration.redis.ToolPlanRunStateStore;
import com.theseus.api.domain.toolgeneration.sse.ToolPlanRunSseEmitterRegistry;
import com.theseus.api.domain.user.entity.SystemRole;
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
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@ExtendWith(MockitoExtension.class)
class ToolPlanRunEventStreamServiceTest {

	private static final Long USER_ID = 10L;
	private static final Long PROJECT_ID = 20L;
	private static final Long CHAT_SESSION_ID = 30L;
	private static final String RUN_ID = "run-254";

	@Mock
	private ToolPlanRunAccessService toolPlanRunAccessService;

	@Mock
	private ToolPlanRunStateStore toolPlanRunStateStore;

	@Mock
	private ToolPlanRunSseEmitterRegistry emitterRegistry;

	private ToolPlanRunEventStreamService service;
	private ToolPlanRun toolPlanRun;

	@BeforeEach
	void setUp() {
		service = new ToolPlanRunEventStreamService(
			toolPlanRunAccessService,
			toolPlanRunStateStore,
			new ToolGenerationStateProperties(30, 1800000),
			emitterRegistry
		);
		toolPlanRun = createRun();
	}

	@Test
	@DisplayName("권한 있는 사용자가 ToolPlanRun SSE를 구독하면 Emitter를 등록하고 connected 이벤트를 전송한다.")
	void subscribe() {
		// Given
		when(toolPlanRunAccessService.getAccessibleRun(createAuthenticatedUser(), PROJECT_ID, CHAT_SESSION_ID, RUN_ID))
			.thenReturn(toolPlanRun);
		when(toolPlanRunStateStore.findByRunId(RUN_ID)).thenReturn(Optional.empty());

		// When
		SseEmitter emitter = service.subscribe(createAuthenticatedUser(), PROJECT_ID, CHAT_SESSION_ID, RUN_ID);

		// Then
		assertThat(emitter).isNotNull();
		verify(emitterRegistry).register(PROJECT_ID, CHAT_SESSION_ID, RUN_ID, emitter);
		ArgumentCaptor<ToolPlanRunSseEvent> eventCaptor = ArgumentCaptor.forClass(ToolPlanRunSseEvent.class);
		verify(emitterRegistry).sendToEmitter(
			same(PROJECT_ID),
			same(CHAT_SESSION_ID),
			same(RUN_ID),
			same(emitter),
			eventCaptor.capture()
		);
		assertThat(eventCaptor.getValue().getEventType()).isEqualTo("connected");
	}

	@Test
	@DisplayName("Redis 최신 상태가 있으면 SSE 연결 직후 최초 상태를 전송한다.")
	void subscribeSendsLatestState() {
		// Given
		when(toolPlanRunAccessService.getAccessibleRun(createAuthenticatedUser(), PROJECT_ID, CHAT_SESSION_ID, RUN_ID))
			.thenReturn(toolPlanRun);
		when(toolPlanRunStateStore.findByRunId(RUN_ID)).thenReturn(Optional.of(ToolPlanRunState.builder()
			.runId(RUN_ID)
			.projectId(PROJECT_ID)
			.chatSessionId(CHAT_SESSION_ID)
			.eventType("progress")
			.status("GENERATING")
			.build()));

		// When
		SseEmitter emitter = service.subscribe(createAuthenticatedUser(), PROJECT_ID, CHAT_SESSION_ID, RUN_ID);

		// Then
		ArgumentCaptor<ToolPlanRunSseEvent> eventCaptor = ArgumentCaptor.forClass(ToolPlanRunSseEvent.class);
		verify(emitterRegistry, org.mockito.Mockito.times(2)).sendToEmitter(
			same(PROJECT_ID),
			same(CHAT_SESSION_ID),
			same(RUN_ID),
			same(emitter),
			eventCaptor.capture()
		);
		assertThat(eventCaptor.getAllValues())
			.extracting(ToolPlanRunSseEvent::getEventType)
			.containsExactly("connected", "progress");
	}

	private AuthenticatedUser createAuthenticatedUser() {
		return new AuthenticatedUser(USER_ID, "A254001", "Run Stream User", SystemRole.USER);
	}

	private ToolPlanRun createRun() {
		User user = User.builder()
			.employeeNumber("A254001")
			.name("Run Stream User")
			.password("encoded-password")
			.build();
		ReflectionTestUtils.setField(user, "id", USER_ID);

		Project project = Project.builder()
			.name("Run Stream Project")
			.createdByUser(user)
			.projectAdminUser(user)
			.build();
		ReflectionTestUtils.setField(project, "id", PROJECT_ID);

		ProjectMember projectMember = ProjectMember.builder()
			.project(project)
			.user(user)
			.projectRole(ProjectRole.ADMIN)
			.build();
		ReflectionTestUtils.setField(projectMember, "id", 40L);

		ChatSession chatSession = ChatSession.builder()
			.project(project)
			.projectMember(projectMember)
			.title("Run Stream Session")
			.build();
		ReflectionTestUtils.setField(chatSession, "id", CHAT_SESSION_ID);

		return ToolPlanRun.builder()
			.runId(RUN_ID)
			.project(project)
			.chatSession(chatSession)
			.requestType(ToolPlanRunRequestType.GENERATE_PLAN)
			.requestedByProjectMember(projectMember)
			.build();
	}
}
