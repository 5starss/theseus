package com.theseus.api.domain.toolgeneration.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
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
import com.theseus.api.domain.toolgeneration.dto.ToolGenerationState;
import com.theseus.api.domain.toolgeneration.dto.response.ToolGenerationStateResponse;
import com.theseus.api.domain.toolgeneration.redis.ToolGenerationStateStore;
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.user.entity.SystemRole;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.time.LocalDateTime;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class ToolGenerationStateServiceTest {

	private static final Long USER_ID = 10L;
	private static final Long PROJECT_ID = 20L;
	private static final Long CHAT_SESSION_ID = 30L;
	private static final Long TOOL_ID = 40L;
	private static final LocalDateTime UPDATED_AT = LocalDateTime.of(2026, 5, 7, 10, 0);

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

	private ToolGenerationStateService service;
	private User user;
	private Project project;
	private ProjectMember projectMember;
	private ChatSession chatSession;
	private Tool tool;

	@BeforeEach
	void setUp() {
		service = new ToolGenerationStateService(
			userRepository,
			projectRepository,
			projectMemberRepository,
			chatSessionRepository,
			toolRepository,
			toolGenerationStateStore
		);
		user = createUser();
		project = createProject(user);
		projectMember = createProjectMember(project, user, ProjectMemberStatus.IN_PROGRESS);
		chatSession = createChatSession(project, projectMember);
		tool = createTool();
	}

	@Test
	@DisplayName("Redis에 Tool 생성 상태가 존재하면 Redis 값을 우선 반환한다.")
	void getToolGenerationStateFromRedis() {
		// Given
		givenAccessibleTool(tool);
		ToolGenerationState state = ToolGenerationState.builder()
			.projectId(PROJECT_ID)
			.chatSessionId(CHAT_SESSION_ID)
			.toolId(TOOL_ID)
			.eventType("progress")
			.status("GENERATING")
			.draftPhase("PLAN")
			.progressRate(65)
			.message("PLAN 명세를 작성하고 있습니다.")
			.draftVersion(1)
			.updatedAt(UPDATED_AT)
			.build();
		when(toolGenerationStateStore.findByToolId(TOOL_ID)).thenReturn(Optional.of(state));

		// When
		ToolGenerationStateResponse response = service.getToolGenerationState(
			createAuthenticatedUser(),
			PROJECT_ID,
			CHAT_SESSION_ID,
			TOOL_ID
		);

		// Then
		assertThat(response.getEventType()).isEqualTo("progress");
		assertThat(response.getStatus()).isEqualTo("GENERATING");
		assertThat(response.getProgressRate()).isEqualTo(65);
		assertThat(response.getDraftVersion()).isEqualTo(1L);
	}

	@Test
	@DisplayName("Redis 상태가 없으면 DRAFT PLAN Tool을 GENERATING 상태로 반환한다.")
	void getToolGenerationStateFallbackWhenDraftPlan() {
		// Given
		givenAccessibleTool(tool);
		when(toolGenerationStateStore.findByToolId(TOOL_ID)).thenReturn(Optional.empty());

		// When
		ToolGenerationStateResponse response = service.getToolGenerationState(
			createAuthenticatedUser(),
			PROJECT_ID,
			CHAT_SESSION_ID,
			TOOL_ID
		);

		// Then
		assertThat(response.getEventType()).isEqualTo("state");
		assertThat(response.getStatus()).isEqualTo("GENERATING");
		assertThat(response.getDraftPhase()).isEqualTo("PLAN");
		assertThat(response.getDraftVersion()).isEqualTo(0L);
	}

	@Test
	@DisplayName("Redis 조회에 실패하면 DB Tool 상태 기반 fallback을 반환한다.")
	void getToolGenerationStateFallbackWhenRedisFails() {
		// Given
		tool.markAsReview();
		givenAccessibleTool(tool);
		when(toolGenerationStateStore.findByToolId(TOOL_ID)).thenThrow(new IllegalStateException("redis error"));

		// When
		ToolGenerationStateResponse response = service.getToolGenerationState(
			createAuthenticatedUser(),
			PROJECT_ID,
			CHAT_SESSION_ID,
			TOOL_ID
		);

		// Then
		assertThat(response.getEventType()).isEqualTo("state");
		assertThat(response.getStatus()).isEqualTo("REVIEW");
		assertThat(response.getDraftPhase()).isEqualTo("REVIEW");
	}

	@Test
	@DisplayName("DRAFT REVIEW Tool은 REVIEW 상태로 fallback된다.")
	void getToolGenerationStateFallbackWhenDraftReview() {
		// Given
		tool.markAsReview();
		givenFallbackTool(tool);

		// When
		ToolGenerationStateResponse response = service.getToolGenerationState(
			createAuthenticatedUser(),
			PROJECT_ID,
			CHAT_SESSION_ID,
			TOOL_ID
		);

		// Then
		assertThat(response.getStatus()).isEqualTo("REVIEW");
		assertThat(response.getDraftPhase()).isEqualTo("REVIEW");
	}

	@Test
	@DisplayName("PENDING Tool은 PENDING 상태로 fallback된다.")
	void getToolGenerationStateFallbackWhenPending() {
		// Given
		tool.markAsReview();
		tool.requestApproval();
		givenFallbackTool(tool);

		// When
		ToolGenerationStateResponse response = service.getToolGenerationState(
			createAuthenticatedUser(),
			PROJECT_ID,
			CHAT_SESSION_ID,
			TOOL_ID
		);

		// Then
		assertThat(response.getStatus()).isEqualTo("PENDING");
	}

	@Test
	@DisplayName("APPROVED Tool은 APPROVED 상태로 fallback된다.")
	void getToolGenerationStateFallbackWhenApproved() {
		// Given
		tool.markAsReview();
		tool.approve(1);
		givenFallbackTool(tool);

		// When
		ToolGenerationStateResponse response = service.getToolGenerationState(
			createAuthenticatedUser(),
			PROJECT_ID,
			CHAT_SESSION_ID,
			TOOL_ID
		);

		// Then
		assertThat(response.getStatus()).isEqualTo("APPROVED");
	}

	@Test
	@DisplayName("REJECTED Tool은 REJECTED 상태로 fallback된다.")
	void getToolGenerationStateFallbackWhenRejected() {
		// Given
		tool.reject();
		givenFallbackTool(tool);

		// When
		ToolGenerationStateResponse response = service.getToolGenerationState(
			createAuthenticatedUser(),
			PROJECT_ID,
			CHAT_SESSION_ID,
			TOOL_ID
		);

		// Then
		assertThat(response.getStatus()).isEqualTo("REJECTED");
	}

	@Test
	@DisplayName("DELETED Tool은 DELETED 상태로 fallback된다.")
	void getToolGenerationStateFallbackWhenDeleted() {
		// Given
		tool.delete();
		givenFallbackTool(tool);

		// When
		ToolGenerationStateResponse response = service.getToolGenerationState(
			createAuthenticatedUser(),
			PROJECT_ID,
			CHAT_SESSION_ID,
			TOOL_ID
		);

		// Then
		assertThat(response.getStatus()).isEqualTo("DELETED");
	}

	@Test
	@DisplayName("비인증 사용자는 Tool 생성 상태 조회에 실패한다.")
	void getToolGenerationStateFailsWhenUnauthenticated() {
		// When & Then
		assertThatThrownBy(() -> service.getToolGenerationState(null, PROJECT_ID, CHAT_SESSION_ID, TOOL_ID))
			.isInstanceOf(BusinessException.class)
			.extracting("errorCode")
			.isEqualTo(ErrorCode.UNAUTHORIZED);
	}

	@Test
	@DisplayName("프로젝트 멤버가 아니면 Tool 생성 상태 조회에 실패한다.")
	void getToolGenerationStateFailsWhenProjectMemberNotFound() {
		// Given
		when(userRepository.findById(USER_ID)).thenReturn(Optional.of(user));
		when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.of(project));
		when(projectMemberRepository.findByProjectAndUser(project, user)).thenReturn(Optional.empty());

		// When & Then
		assertThatThrownBy(() -> service.getToolGenerationState(
			createAuthenticatedUser(),
			PROJECT_ID,
			CHAT_SESSION_ID,
			TOOL_ID
		))
			.isInstanceOf(BusinessException.class)
			.extracting("errorCode")
			.isEqualTo(ErrorCode.PROJECT_MEMBER_PERMISSION_REQUIRED);
	}

	@Test
	@DisplayName("진행 중인 프로젝트 멤버가 아니면 Tool 생성 상태 조회에 실패한다.")
	void getToolGenerationStateFailsWhenProjectMemberIsNotActive() {
		// Given
		projectMember = createProjectMember(project, user, ProjectMemberStatus.COMPLETED);
		when(userRepository.findById(USER_ID)).thenReturn(Optional.of(user));
		when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.of(project));
		when(projectMemberRepository.findByProjectAndUser(project, user)).thenReturn(Optional.of(projectMember));

		// When & Then
		assertThatThrownBy(() -> service.getToolGenerationState(
			createAuthenticatedUser(),
			PROJECT_ID,
			CHAT_SESSION_ID,
			TOOL_ID
		))
			.isInstanceOf(BusinessException.class)
			.extracting("errorCode")
			.isEqualTo(ErrorCode.ACTIVE_PROJECT_MEMBER_REQUIRED);
	}

	@Test
	@DisplayName("다른 프로젝트의 채팅 세션으로 Tool 생성 상태를 조회하면 실패한다.")
	void getToolGenerationStateFailsWhenSessionDoesNotBelongToProject() {
		// Given
		when(userRepository.findById(USER_ID)).thenReturn(Optional.of(user));
		when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.of(project));
		when(projectMemberRepository.findByProjectAndUser(project, user)).thenReturn(Optional.of(projectMember));
		when(chatSessionRepository.findByIdAndProject(CHAT_SESSION_ID, project)).thenReturn(Optional.empty());

		// When & Then
		assertThatThrownBy(() -> service.getToolGenerationState(
			createAuthenticatedUser(),
			PROJECT_ID,
			CHAT_SESSION_ID,
			TOOL_ID
		))
			.isInstanceOf(BusinessException.class)
			.extracting("errorCode")
			.isEqualTo(ErrorCode.CHAT_SESSION_NOT_FOUND);
	}

	@Test
	@DisplayName("다른 프로젝트의 Tool 생성 상태는 조회할 수 없다.")
	void getToolGenerationStateFailsWhenToolDoesNotBelongToProject() {
		// Given
		givenAccessibleSession();
		when(toolRepository.findByIdAndProjectAndChatSession(TOOL_ID, project, chatSession))
			.thenReturn(Optional.empty());

		// When & Then
		assertThatThrownBy(() -> service.getToolGenerationState(
			createAuthenticatedUser(),
			PROJECT_ID,
			CHAT_SESSION_ID,
			TOOL_ID
		))
			.isInstanceOf(BusinessException.class)
			.extracting("errorCode")
			.isEqualTo(ErrorCode.TOOL_CHAT_SESSION_MISMATCH);
	}

	@Test
	@DisplayName("다른 채팅 세션의 Tool 생성 상태는 조회할 수 없다.")
	void getToolGenerationStateFailsWhenToolDoesNotBelongToChatSession() {
		// Given
		givenAccessibleSession();
		when(toolRepository.findByIdAndProjectAndChatSession(TOOL_ID, project, chatSession))
			.thenReturn(Optional.empty());

		// When & Then
		assertThatThrownBy(() -> service.getToolGenerationState(
			createAuthenticatedUser(),
			PROJECT_ID,
			CHAT_SESSION_ID,
			TOOL_ID
		))
			.isInstanceOf(BusinessException.class)
			.extracting("errorCode")
			.isEqualTo(ErrorCode.TOOL_CHAT_SESSION_MISMATCH);
	}

	private void givenFallbackTool(Tool accessibleTool) {
		givenAccessibleTool(accessibleTool);
		when(toolGenerationStateStore.findByToolId(TOOL_ID)).thenReturn(Optional.empty());
	}

	private void givenAccessibleTool(Tool accessibleTool) {
		givenAccessibleSession();
		when(toolRepository.findByIdAndProjectAndChatSession(TOOL_ID, project, chatSession))
			.thenReturn(Optional.of(accessibleTool));
	}

	private void givenAccessibleSession() {
		when(userRepository.findById(USER_ID)).thenReturn(Optional.of(user));
		when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.of(project));
		when(projectMemberRepository.findByProjectAndUser(project, user)).thenReturn(Optional.of(projectMember));
		when(chatSessionRepository.findByIdAndProject(CHAT_SESSION_ID, project)).thenReturn(Optional.of(chatSession));
	}

	private AuthenticatedUser createAuthenticatedUser() {
		return new AuthenticatedUser(USER_ID, "A210001", "State User", SystemRole.USER);
	}

	private User createUser() {
		User createdUser = User.builder()
			.employeeNumber("A210001")
			.name("State User")
			.password("encoded-password")
			.build();
		ReflectionTestUtils.setField(createdUser, "id", USER_ID);
		return createdUser;
	}

	private Project createProject(User createdByUser) {
		Project createdProject = Project.builder()
			.name("State Project")
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
			.title("State Session")
			.build();
		ReflectionTestUtils.setField(session, "id", CHAT_SESSION_ID);
		return session;
	}

	private Tool createTool() {
		Tool createdTool = Tool.builder()
			.project(project)
			.chatSession(chatSession)
			.createdByProjectMember(projectMember)
			.fileName("state-tool")
			.build();
		ReflectionTestUtils.setField(createdTool, "id", TOOL_ID);
		ReflectionTestUtils.setField(createdTool, "updatedAt", UPDATED_AT);
		return createdTool;
	}
}
