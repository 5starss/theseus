package com.theseus.api.domain.chat.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.config.CoreStreamProperties;
import com.theseus.api.domain.chat.dto.request.ChatStreamRequest;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.chat.repository.ChatSessionRepository;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.tool.entity.ToolPlanMode;
import com.theseus.api.domain.user.entity.SystemRole;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

@ExtendWith(MockitoExtension.class)
class ChatStreamServiceTest {

	private static final Long USER_ID = 10L;
	private static final Long PROJECT_ID = 20L;
	private static final Long SESSION_ID = 30L;
	private static final String AUTHORIZATION_HEADER = "Bearer access-token";

	@Mock
	private UserRepository userRepository;

	@Mock
	private ProjectRepository projectRepository;

	@Mock
	private ProjectMemberRepository projectMemberRepository;

	@Mock
	private ChatSessionRepository chatSessionRepository;

	private ChatStreamService service;
	private User user;
	private Project project;
	private ChatSession chatSession;

	@BeforeEach
	void setUp() {
		service = new ChatStreamService(
			new CoreStreamProperties("http://localhost:8086"),
			userRepository,
			projectRepository,
			projectMemberRepository,
			chatSessionRepository,
			new ObjectMapper()
		);
		user = User.builder()
			.employeeNumber("A001")
			.name("tester")
			.password("password")
			.systemRole(SystemRole.USER)
			.build();
		project = Project.builder()
			.name("project")
			.createdByUser(user)
			.projectAdminUser(user)
			.build();
		chatSession = ChatSession.builder()
			.project(project)
			.projectMember(createProjectMember(true))
			.title("session")
			.build();
	}

	@Test
	@DisplayName("ASK 모드는 Tool 사용 권한 없이도 Core 스트림 프록시를 생성한다.")
	void streamAskWithoutToolUsePermission() {
		// Given
		ProjectMember projectMember = createProjectMember(false);
		stubAccessibleSession(projectMember);
		ChatStreamRequest request = createRequest(ToolPlanMode.ASK);

		// When
		StreamingResponseBody responseBody = service.streamChat(
			createAuthenticatedUser(),
			PROJECT_ID,
			SESSION_ID,
			request,
			AUTHORIZATION_HEADER
		);

		// Then
		assertThat(responseBody).isNotNull();
	}

	@Test
	@DisplayName("AGENT 모드는 Tool 사용 권한이 없으면 거부한다.")
	void streamAgentRequiresToolUsePermission() {
		// Given
		ProjectMember projectMember = createProjectMember(false);
		stubAccessibleSession(projectMember);
		ChatStreamRequest request = createRequest(ToolPlanMode.AGENT);

		// When & Then
		assertThatThrownBy(() -> service.streamChat(
			createAuthenticatedUser(),
			PROJECT_ID,
			SESSION_ID,
			request,
			AUTHORIZATION_HEADER
		))
			.isInstanceOf(BusinessException.class)
			.extracting("errorCode")
			.isEqualTo(ErrorCode.TOOL_USE_PERMISSION_REQUIRED);
	}

	@Test
	@DisplayName("PLAN 모드는 채팅 스트림 엔드포인트에서 거부한다.")
	void streamPlanModeIsRejected() {
		// Given
		ChatStreamRequest request = createRequest(ToolPlanMode.PLAN);

		// When & Then
		assertThatThrownBy(() -> service.streamChat(
			createAuthenticatedUser(),
			PROJECT_ID,
			SESSION_ID,
			request,
			AUTHORIZATION_HEADER
		))
			.isInstanceOf(BusinessException.class)
			.extracting("errorCode")
			.isEqualTo(ErrorCode.CHAT_STREAM_MODE_INVALID);
	}

	private void stubAccessibleSession(ProjectMember projectMember) {
		when(userRepository.findById(USER_ID)).thenReturn(Optional.of(user));
		when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.of(project));
		when(projectMemberRepository.findByProjectAndUser(project, user)).thenReturn(Optional.of(projectMember));
		when(chatSessionRepository.findByIdAndProjectAndProjectMember(SESSION_ID, project, projectMember))
			.thenReturn(Optional.of(chatSession));
	}

	private ProjectMember createProjectMember(boolean canUseTool) {
		return ProjectMember.builder()
			.project(project)
			.user(user)
			.projectRole(ProjectRole.MEMBER)
			.accessLevel(1)
			.canUseTool(canUseTool)
			.status(ProjectMemberStatus.IN_PROGRESS)
			.build();
	}

	private AuthenticatedUser createAuthenticatedUser() {
		return new AuthenticatedUser(USER_ID, "A001", "tester", SystemRole.USER);
	}

	private ChatStreamRequest createRequest(ToolPlanMode mode) {
		ChatStreamRequest request = new ChatStreamRequest();
		ReflectionTestUtils.setField(request, "mode", mode);
		ReflectionTestUtils.setField(request, "prompt", "hello");
		return request;
	}
}
