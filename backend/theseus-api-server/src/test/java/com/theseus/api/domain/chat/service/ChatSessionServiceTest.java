package com.theseus.api.domain.chat.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.dto.response.ChatSessionDetailResponse;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.chat.repository.ChatMessageRepository;
import com.theseus.api.domain.chat.repository.ChatSessionRepository;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolPlan;
import com.theseus.api.domain.tool.entity.ToolPlanGroup;
import com.theseus.api.domain.tool.entity.ToolPlanGroupStatus;
import com.theseus.api.domain.tool.entity.ToolPlanRun;
import com.theseus.api.domain.tool.entity.ToolPlanRunRequestType;
import com.theseus.api.domain.tool.entity.ToolPlanRunStatus;
import com.theseus.api.domain.tool.entity.ToolPlanStatus;
import com.theseus.api.domain.tool.entity.ToolStatus;
import com.theseus.api.domain.tool.repository.ToolPlanGroupRepository;
import com.theseus.api.domain.tool.repository.ToolPlanRepository;
import com.theseus.api.domain.tool.repository.ToolPlanRunRepository;
import com.theseus.api.domain.user.entity.SystemRole;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class ChatSessionServiceTest {

	private static final Long USER_ID = 10L;
	private static final Long PROJECT_ID = 20L;
	private static final Long PROJECT_MEMBER_ID = 30L;
	private static final Long CHAT_SESSION_ID = 40L;

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
	private ToolPlanRunRepository toolPlanRunRepository;

	@Mock
	private ToolPlanRepository toolPlanRepository;

	@Mock
	private ToolPlanGroupRepository toolPlanGroupRepository;

	private ChatSessionService service;
	private TestFixture fixture;

	@BeforeEach
	void setUp() {
		service = new ChatSessionService(
			chatSessionRepository,
			chatMessageRepository,
			projectRepository,
			projectMemberRepository,
			userRepository,
			toolPlanRunRepository,
			toolPlanRepository,
			toolPlanGroupRepository
		);
		fixture = createFixture();
	}

	@Test
	@DisplayName("채팅 세션 상세 조회 시 진행 중인 ToolPlanRun을 우선 복구한다.")
	void getChatSessionWithRunningToolPlanRun() {
		// Given
		ToolPlanRun runningRun = createToolPlanRun(fixture, "run-256", ToolPlanRunStatus.GENERATING);
		stubAccessibleSession();
		when(chatMessageRepository.findByChatSessionOrderByMessageOrderAsc(fixture.chatSession()))
			.thenReturn(List.of());
		when(toolPlanRunRepository.findFirstByProjectAndChatSessionAndStatusInOrderByUpdatedAtDesc(
			fixture.project(),
			fixture.chatSession(),
			List.of(ToolPlanRunStatus.REQUESTED, ToolPlanRunStatus.GENERATING)
		)).thenReturn(Optional.of(runningRun));

		// When
		ChatSessionDetailResponse response = service.getChatSession(
			createAuthenticatedUser(),
			PROJECT_ID,
			CHAT_SESSION_ID
		);

		// Then
		assertThat(response.getCurrentPlan()).isNotNull();
		assertThat(response.getCurrentPlan().getRunId()).isEqualTo("run-256");
		assertThat(response.getCurrentPlan().getStatus()).isEqualTo("GENERATING");
		assertThat(response.getCreatedTool()).isNull();
		verify(toolPlanRepository, never()).findFirstByProjectAndChatSessionAndStatusInOrderByUpdatedAtDesc(
			any(),
			any(),
			any()
		);
	}

	@Test
	@DisplayName("진행 중인 run이 없으면 최신 REVIEW ToolPlan을 복구한다.")
	void getChatSessionWithReviewToolPlan() {
		// Given
		ToolPlanGroup planGroup = createToolPlanGroup(fixture, ToolPlanGroupStatus.REVIEW);
		ToolPlan toolPlan = createToolPlan(fixture, planGroup, 2L, ToolPlanStatus.REVIEW);
		stubAccessibleSession();
		when(chatMessageRepository.findByChatSessionOrderByMessageOrderAsc(fixture.chatSession()))
			.thenReturn(List.of());
		when(toolPlanRunRepository.findFirstByProjectAndChatSessionAndStatusInOrderByUpdatedAtDesc(
			fixture.project(),
			fixture.chatSession(),
			List.of(ToolPlanRunStatus.REQUESTED, ToolPlanRunStatus.GENERATING)
		)).thenReturn(Optional.empty());
		when(toolPlanRepository.findFirstByProjectAndChatSessionAndStatusInOrderByUpdatedAtDesc(
			fixture.project(),
			fixture.chatSession(),
			displayableToolPlanStatuses()
		)).thenReturn(Optional.of(toolPlan));

		// When
		ChatSessionDetailResponse response = service.getChatSession(
			createAuthenticatedUser(),
			PROJECT_ID,
			CHAT_SESSION_ID
		);

		// Then
		assertThat(response.getCurrentPlan()).isNotNull();
		assertThat(response.getCurrentPlan().getToolPlanGroupId()).isEqualTo(70L);
		assertThat(response.getCurrentPlan().getToolPlanId()).isEqualTo(80L);
		assertThat(response.getCurrentPlan().getPlanVersion()).isEqualTo(2L);
		assertThat(response.getCurrentPlan().getStatus()).isEqualTo("REVIEW");
	}

	@Test
	@DisplayName("복구할 run과 REVIEW ToolPlan이 없으면 생성 완료 Tool을 복구한다.")
	void getChatSessionWithBuiltTool() {
		// Given
		ToolPlanGroup planGroup = createToolPlanGroup(fixture, ToolPlanGroupStatus.BUILT);
		ToolPlan toolPlan = createToolPlan(fixture, planGroup, 1L, ToolPlanStatus.APPROVED);
		Tool tool = createTool(fixture, toolPlan);
		ReflectionTestUtils.setField(planGroup, "createdTool", tool);
		stubAccessibleSession();
		when(chatMessageRepository.findByChatSessionOrderByMessageOrderAsc(fixture.chatSession()))
			.thenReturn(List.of());
		when(toolPlanRunRepository.findFirstByProjectAndChatSessionAndStatusInOrderByUpdatedAtDesc(
			fixture.project(),
			fixture.chatSession(),
			List.of(ToolPlanRunStatus.REQUESTED, ToolPlanRunStatus.GENERATING)
		)).thenReturn(Optional.empty());
		when(toolPlanRepository.findFirstByProjectAndChatSessionAndStatusInOrderByUpdatedAtDesc(
			fixture.project(),
			fixture.chatSession(),
			displayableToolPlanStatuses()
		)).thenReturn(Optional.empty());
		when(toolPlanGroupRepository.findFirstByProjectAndChatSessionAndStatusOrderByUpdatedAtDesc(
			fixture.project(),
			fixture.chatSession(),
			ToolPlanGroupStatus.BUILT
		)).thenReturn(Optional.of(planGroup));

		// When
		ChatSessionDetailResponse response = service.getChatSession(
			createAuthenticatedUser(),
			PROJECT_ID,
			CHAT_SESSION_ID
		);

		// Then
		assertThat(response.getCurrentPlan()).isNull();
		assertThat(response.getCreatedTool()).isNotNull();
		assertThat(response.getCreatedTool().getToolId()).isEqualTo(90L);
		assertThat(response.getCreatedTool().getSourceToolPlanId()).isEqualTo(80L);
		assertThat(response.getCreatedTool().getStatus()).isEqualTo("APPROVED");
	}

	@Test
	@DisplayName("빌드 실패 상태에서도 승인된 ToolPlan을 패널 복구 대상으로 포함한다.")
	void getChatSessionWithApprovedToolPlanAfterBuildFailure() {
		// Given
		ToolPlanGroup planGroup = createToolPlanGroup(fixture, ToolPlanGroupStatus.FAILED);
		ToolPlan toolPlan = createToolPlan(fixture, planGroup, 3L, ToolPlanStatus.APPROVED);
		stubAccessibleSession();
		when(chatMessageRepository.findByChatSessionOrderByMessageOrderAsc(fixture.chatSession()))
			.thenReturn(List.of());
		when(toolPlanRunRepository.findFirstByProjectAndChatSessionAndStatusInOrderByUpdatedAtDesc(
			fixture.project(),
			fixture.chatSession(),
			List.of(ToolPlanRunStatus.REQUESTED, ToolPlanRunStatus.GENERATING)
		)).thenReturn(Optional.empty());
		when(toolPlanRepository.findFirstByProjectAndChatSessionAndStatusInOrderByUpdatedAtDesc(
			fixture.project(),
			fixture.chatSession(),
			displayableToolPlanStatuses()
		)).thenReturn(Optional.of(toolPlan));

		// When
		ChatSessionDetailResponse response = service.getChatSession(
			createAuthenticatedUser(),
			PROJECT_ID,
			CHAT_SESSION_ID
		);

		// Then
		assertThat(response.getCurrentPlan()).isNotNull();
		assertThat(response.getCurrentPlan().getToolPlanGroupId()).isEqualTo(70L);
		assertThat(response.getCurrentPlan().getToolPlanId()).isEqualTo(80L);
		assertThat(response.getCurrentPlan().getPlanVersion()).isEqualTo(3L);
		assertThat(response.getCurrentPlan().getStatus()).isEqualTo("APPROVED");
		assertThat(response.getCreatedTool()).isNull();
		verify(toolPlanGroupRepository, never()).findFirstByProjectAndChatSessionAndStatusOrderByUpdatedAtDesc(
			any(),
			any(),
			any()
		);
	}

	private void stubAccessibleSession() {
		when(userRepository.findById(USER_ID)).thenReturn(Optional.of(fixture.user()));
		when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.of(fixture.project()));
		when(projectMemberRepository.findByProjectAndUser(fixture.project(), fixture.user()))
			.thenReturn(Optional.of(fixture.projectMember()));
		when(chatSessionRepository.findByIdAndProjectAndProjectMember(
			CHAT_SESSION_ID,
			fixture.project(),
			fixture.projectMember()
		)).thenReturn(Optional.of(fixture.chatSession()));
	}

	private List<ToolPlanStatus> displayableToolPlanStatuses() {
		return List.of(
			ToolPlanStatus.REVIEW,
			ToolPlanStatus.PENDING,
			ToolPlanStatus.APPROVED,
			ToolPlanStatus.REJECTED
		);
	}

	private AuthenticatedUser createAuthenticatedUser() {
		return new AuthenticatedUser(USER_ID, "A256001", "Session Recovery User", SystemRole.USER);
	}

	private TestFixture createFixture() {
		User user = User.builder()
			.employeeNumber("A256001")
			.name("Session Recovery User")
			.password("encoded-password")
			.build();
		ReflectionTestUtils.setField(user, "id", USER_ID);

		Project project = Project.builder()
			.name("Session Recovery Project")
			.createdByUser(user)
			.projectAdminUser(user)
			.build();
		ReflectionTestUtils.setField(project, "id", PROJECT_ID);

		ProjectMember projectMember = ProjectMember.builder()
			.project(project)
			.user(user)
			.projectRole(ProjectRole.ADMIN)
			.canCreateTool(true)
			.build();
		ReflectionTestUtils.setField(projectMember, "id", PROJECT_MEMBER_ID);

		ChatSession chatSession = ChatSession.builder()
			.project(project)
			.projectMember(projectMember)
			.title("Session Recovery")
			.build();
		ReflectionTestUtils.setField(chatSession, "id", CHAT_SESSION_ID);

		return new TestFixture(user, project, projectMember, chatSession);
	}

	private ToolPlanRun createToolPlanRun(TestFixture fixture, String runId, ToolPlanRunStatus status) {
		ToolPlanRun toolPlanRun = ToolPlanRun.builder()
			.runId(runId)
			.project(fixture.project())
			.chatSession(fixture.chatSession())
			.requestType(ToolPlanRunRequestType.GENERATE_PLAN)
			.status(status)
			.requestedByProjectMember(fixture.projectMember())
			.build();
		ReflectionTestUtils.setField(toolPlanRun, "id", 60L);
		return toolPlanRun;
	}

	private ToolPlanGroup createToolPlanGroup(TestFixture fixture, ToolPlanGroupStatus status) {
		ToolPlanGroup planGroup = ToolPlanGroup.builder()
			.project(fixture.project())
			.chatSession(fixture.chatSession())
			.createdByProjectMember(fixture.projectMember())
			.status(status)
			.build();
		ReflectionTestUtils.setField(planGroup, "id", 70L);
		return planGroup;
	}

	private ToolPlan createToolPlan(
		TestFixture fixture,
		ToolPlanGroup planGroup,
		Long planVersion,
		ToolPlanStatus status
	) {
		ToolPlan toolPlan = ToolPlan.builder()
			.planGroup(planGroup)
			.project(fixture.project())
			.chatSession(fixture.chatSession())
			.createdByProjectMember(fixture.projectMember())
			.planVersion(planVersion)
			.status(status)
			.rawMarkdown("PLAN")
			.structuredPlanJson("{\"blocks\":[]}")
			.planSnapshot("{\"schemaVersion\":\"1.0\"}")
			.build();
		ReflectionTestUtils.setField(toolPlan, "id", 80L);
		return toolPlan;
	}

	private Tool createTool(TestFixture fixture, ToolPlan toolPlan) {
		Tool tool = Tool.builder()
			.project(fixture.project())
			.chatSession(fixture.chatSession())
			.createdByProjectMember(fixture.projectMember())
			.sourceToolPlan(toolPlan)
			.fileName("session_recovery_tool.py")
			.status(ToolStatus.APPROVED)
			.build();
		ReflectionTestUtils.setField(tool, "id", 90L);
		return tool;
	}

	private record TestFixture(
		User user,
		Project project,
		ProjectMember projectMember,
		ChatSession chatSession
	) {
	}
}
