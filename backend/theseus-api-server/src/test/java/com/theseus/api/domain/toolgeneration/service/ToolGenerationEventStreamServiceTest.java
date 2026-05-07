package com.theseus.api.domain.toolgeneration.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.same;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.chat.repository.ChatSessionRepository;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.toolgeneration.config.ToolGenerationStateProperties;
import com.theseus.api.domain.toolgeneration.dto.ToolGenerationSseEvent;
import com.theseus.api.domain.toolgeneration.dto.ToolGenerationState;
import com.theseus.api.domain.toolgeneration.redis.ToolGenerationStateStore;
import com.theseus.api.domain.toolgeneration.sse.ToolGenerationSseEmitterRegistry;
import com.theseus.api.domain.user.entity.SystemRole;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
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
class ToolGenerationEventStreamServiceTest {

	private static final Long USER_ID = 10L;
	private static final Long PROJECT_ID = 20L;
	private static final Long CHAT_SESSION_ID = 30L;
	private static final Long TOOL_ID = 40L;

	@Mock
	private UserRepository userRepository;

	@Mock
	private ProjectRepository projectRepository;

	@Mock
	private ProjectMemberRepository projectMemberRepository;

	@Mock
	private ChatSessionRepository chatSessionRepository;

	@Mock
	private ToolRepository toolRepository;

	@Mock
	private ToolGenerationStateStore toolGenerationStateStore;

	@Mock
	private ToolGenerationSseEmitterRegistry emitterRegistry;

	private ToolGenerationEventStreamService service;
	private User user;
	private Project project;
	private ProjectMember projectMember;
	private ChatSession chatSession;
	private Tool tool;

	@BeforeEach
	void setUp() {
		service = new ToolGenerationEventStreamService(
			userRepository,
			projectRepository,
			projectMemberRepository,
			chatSessionRepository,
			toolRepository,
			toolGenerationStateStore,
			new ToolGenerationStateProperties(30, 1800000),
			emitterRegistry
		);
		user = createUser();
		project = createProject(user);
		projectMember = createProjectMember(project, user, ProjectMemberStatus.IN_PROGRESS);
		chatSession = createChatSession(project, projectMember);
		tool = createTool(project, chatSession, projectMember);
	}

	@Test
	@DisplayName("권한 있는 프로젝트 멤버가 Tool 생성 SSE를 구독하면 Emitter를 등록하고 connected 이벤트를 전송한다.")
	void subscribe() {
		// Given
		givenAccessibleTool();
		when(toolGenerationStateStore.findByToolId(TOOL_ID)).thenReturn(Optional.empty());

		// When
		SseEmitter emitter = service.subscribe(createAuthenticatedUser(), PROJECT_ID, CHAT_SESSION_ID, TOOL_ID);

		// Then
		assertThat(emitter).isNotNull();
		verify(emitterRegistry).register(PROJECT_ID, CHAT_SESSION_ID, TOOL_ID, emitter);
		ArgumentCaptor<ToolGenerationSseEvent> eventCaptor = ArgumentCaptor.forClass(ToolGenerationSseEvent.class);
		verify(emitterRegistry).sendToEmitter(
			same(PROJECT_ID),
			same(CHAT_SESSION_ID),
			same(TOOL_ID),
			same(emitter),
			eventCaptor.capture()
		);
		assertThat(eventCaptor.getValue().getEventType()).isEqualTo("connected");
	}

	@Test
	@DisplayName("Redis에 최신 Tool 생성 상태가 있으면 SSE 연결 직후 최초 상태를 전송한다.")
	void subscribeSendsLatestState() {
		// Given
		givenAccessibleTool();
		ToolGenerationState state = ToolGenerationState.builder()
			.projectId(PROJECT_ID)
			.chatSessionId(CHAT_SESSION_ID)
			.toolId(TOOL_ID)
			.eventType("progress")
			.status("GENERATING")
			.progressRate(50)
			.build();
		when(toolGenerationStateStore.findByToolId(TOOL_ID)).thenReturn(Optional.of(state));

		// When
		SseEmitter emitter = service.subscribe(createAuthenticatedUser(), PROJECT_ID, CHAT_SESSION_ID, TOOL_ID);

		// Then
		ArgumentCaptor<ToolGenerationSseEvent> eventCaptor = ArgumentCaptor.forClass(ToolGenerationSseEvent.class);
		verify(emitterRegistry, org.mockito.Mockito.times(2)).sendToEmitter(
			same(PROJECT_ID),
			same(CHAT_SESSION_ID),
			same(TOOL_ID),
			same(emitter),
			eventCaptor.capture()
		);
		assertThat(eventCaptor.getAllValues())
			.extracting(ToolGenerationSseEvent::getEventType)
			.containsExactly("connected", "progress");
	}

	@Test
	@DisplayName("비인증 사용자는 Tool 생성 SSE 구독에 실패한다.")
	void subscribeFailsWhenUnauthenticated() {
		// When & Then
		assertThatThrownBy(() -> service.subscribe(null, PROJECT_ID, CHAT_SESSION_ID, TOOL_ID))
			.isInstanceOf(BusinessException.class)
			.extracting("errorCode")
			.isEqualTo(ErrorCode.UNAUTHORIZED);
	}

	@Test
	@DisplayName("프로젝트 멤버가 아니면 Tool 생성 SSE 구독에 실패한다.")
	void subscribeFailsWhenProjectMemberNotFound() {
		// Given
		when(userRepository.findById(USER_ID)).thenReturn(Optional.of(user));
		when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.of(project));
		when(projectMemberRepository.findByProjectAndUser(project, user)).thenReturn(Optional.empty());

		// When & Then
		assertThatThrownBy(() -> service.subscribe(createAuthenticatedUser(), PROJECT_ID, CHAT_SESSION_ID, TOOL_ID))
			.isInstanceOf(BusinessException.class)
			.extracting("errorCode")
			.isEqualTo(ErrorCode.PROJECT_MEMBER_PERMISSION_REQUIRED);
	}

	@Test
	@DisplayName("진행 중인 프로젝트 멤버가 아니면 Tool 생성 SSE 구독에 실패한다.")
	void subscribeFailsWhenProjectMemberIsNotActive() {
		// Given
		projectMember = createProjectMember(project, user, ProjectMemberStatus.COMPLETED);
		when(userRepository.findById(USER_ID)).thenReturn(Optional.of(user));
		when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.of(project));
		when(projectMemberRepository.findByProjectAndUser(project, user)).thenReturn(Optional.of(projectMember));

		// When & Then
		assertThatThrownBy(() -> service.subscribe(createAuthenticatedUser(), PROJECT_ID, CHAT_SESSION_ID, TOOL_ID))
			.isInstanceOf(BusinessException.class)
			.extracting("errorCode")
			.isEqualTo(ErrorCode.ACTIVE_PROJECT_MEMBER_REQUIRED);
	}

	@Test
	@DisplayName("ChatSession이 요청한 프로젝트에 속하지 않으면 Tool 생성 SSE 구독에 실패한다.")
	void subscribeFailsWhenSessionDoesNotBelongToProject() {
		// Given
		when(userRepository.findById(USER_ID)).thenReturn(Optional.of(user));
		when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.of(project));
		when(projectMemberRepository.findByProjectAndUser(project, user)).thenReturn(Optional.of(projectMember));
		when(chatSessionRepository.findByIdAndProject(CHAT_SESSION_ID, project)).thenReturn(Optional.empty());

		// When & Then
		assertThatThrownBy(() -> service.subscribe(createAuthenticatedUser(), PROJECT_ID, CHAT_SESSION_ID, TOOL_ID))
			.isInstanceOf(BusinessException.class)
			.extracting("errorCode")
			.isEqualTo(ErrorCode.CHAT_SESSION_NOT_FOUND);
	}

	@Test
	@DisplayName("Tool이 요청한 프로젝트와 채팅 세션에 속하지 않으면 SSE 구독에 실패한다.")
	void subscribeFailsWhenToolDoesNotBelongToSession() {
		// Given
		givenAccessibleSession();
		when(toolRepository.findByIdAndProjectAndChatSession(TOOL_ID, project, chatSession))
			.thenReturn(Optional.empty());

		// When & Then
		assertThatThrownBy(() -> service.subscribe(createAuthenticatedUser(), PROJECT_ID, CHAT_SESSION_ID, TOOL_ID))
			.isInstanceOf(BusinessException.class)
			.extracting("errorCode")
			.isEqualTo(ErrorCode.TOOL_CHAT_SESSION_MISMATCH);
	}

	private void givenAccessibleTool() {
		givenAccessibleSession();
		when(toolRepository.findByIdAndProjectAndChatSession(TOOL_ID, project, chatSession))
			.thenReturn(Optional.of(tool));
	}

	private void givenAccessibleSession() {
		when(userRepository.findById(USER_ID)).thenReturn(Optional.of(user));
		when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.of(project));
		when(projectMemberRepository.findByProjectAndUser(project, user)).thenReturn(Optional.of(projectMember));
		when(chatSessionRepository.findByIdAndProject(CHAT_SESSION_ID, project)).thenReturn(Optional.of(chatSession));
	}

	private AuthenticatedUser createAuthenticatedUser() {
		return new AuthenticatedUser(USER_ID, "A199001", "SSE User", SystemRole.USER);
	}

	private User createUser() {
		User createdUser = User.builder()
			.employeeNumber("A199001")
			.name("SSE User")
			.password("encoded-password")
			.build();
		ReflectionTestUtils.setField(createdUser, "id", USER_ID);
		return createdUser;
	}

	private Project createProject(User createdByUser) {
		Project createdProject = Project.builder()
			.name("SSE Project")
			.createdByUser(createdByUser)
			.projectAdminUser(createdByUser)
			.build();
		ReflectionTestUtils.setField(createdProject, "id", PROJECT_ID);
		return createdProject;
	}

	private ProjectMember createProjectMember(Project memberProject, User memberUser, ProjectMemberStatus status) {
		ProjectMember member = ProjectMember.builder()
			.project(memberProject)
			.user(memberUser)
			.projectRole(ProjectRole.MEMBER)
			.status(status)
			.build();
		ReflectionTestUtils.setField(member, "id", 50L);
		return member;
	}

	private ChatSession createChatSession(Project sessionProject, ProjectMember sessionProjectMember) {
		ChatSession session = ChatSession.builder()
			.project(sessionProject)
			.projectMember(sessionProjectMember)
			.title("SSE Session")
			.build();
		ReflectionTestUtils.setField(session, "id", CHAT_SESSION_ID);
		return session;
	}

	private Tool createTool(Project toolProject, ChatSession toolChatSession, ProjectMember createdByProjectMember) {
		Tool createdTool = Tool.builder()
			.project(toolProject)
			.chatSession(toolChatSession)
			.createdByProjectMember(createdByProjectMember)
			.fileName("sse-tool")
			.build();
		ReflectionTestUtils.setField(createdTool, "id", TOOL_ID);
		return createdTool;
	}
}
