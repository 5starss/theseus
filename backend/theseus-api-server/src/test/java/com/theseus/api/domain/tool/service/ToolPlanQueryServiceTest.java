package com.theseus.api.domain.tool.service;

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
import com.theseus.api.domain.tool.dto.response.ToolPlanDetailResponse;
import com.theseus.api.domain.tool.entity.ToolPlan;
import com.theseus.api.domain.tool.entity.ToolPlanGroup;
import com.theseus.api.domain.tool.entity.ToolPlanGroupStatus;
import com.theseus.api.domain.tool.entity.ToolPlanStatus;
import com.theseus.api.domain.tool.repository.ToolPlanRepository;
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

@ExtendWith(MockitoExtension.class)
class ToolPlanQueryServiceTest {

	private static final Long USER_ID = 1L;
	private static final Long PROJECT_ID = 2L;
	private static final Long SESSION_ID = 3L;
	private static final Long TOOL_PLAN_GROUP_ID = 4L;
	private static final Long TOOL_PLAN_ID = 5L;

	@Mock
	private UserRepository userRepository;

	@Mock
	private ProjectRepository projectRepository;

	@Mock
	private ProjectMemberRepository projectMemberRepository;

	@Mock
	private ChatSessionRepository chatSessionRepository;

	@Mock
	private ToolPlanRepository toolPlanRepository;

	private ToolPlanQueryService service;
	private User user;
	private Project project;
	private ProjectMember projectMember;
	private ChatSession chatSession;
	private ToolPlan toolPlan;

	@BeforeEach
	void setUp() {
		service = new ToolPlanQueryService(
			userRepository,
			projectRepository,
			projectMemberRepository,
			chatSessionRepository,
			toolPlanRepository
		);
		user = createUser();
		project = createProject(user);
		projectMember = createProjectMember(project, user, ProjectMemberStatus.IN_PROGRESS);
		chatSession = createChatSession(project, projectMember);
		toolPlan = createToolPlan(project, projectMember, chatSession);
	}

	@Test
	@DisplayName("활성 프로젝트 멤버는 ToolPlan 상세 정보를 조회할 수 있다.")
	void getToolPlanDetail() {
		// Given
		when(userRepository.findById(USER_ID)).thenReturn(Optional.of(user));
		when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.of(project));
		when(projectMemberRepository.findByProjectAndUser(project, user)).thenReturn(Optional.of(projectMember));
		when(chatSessionRepository.findByIdAndProject(SESSION_ID, project)).thenReturn(Optional.of(chatSession));
		when(toolPlanRepository.findByIdAndProjectAndChatSession(TOOL_PLAN_ID, project, chatSession))
			.thenReturn(Optional.of(toolPlan));

		// When
		ToolPlanDetailResponse response = service.getToolPlanDetail(
			createAuthenticatedUser(),
			PROJECT_ID,
			SESSION_ID,
			TOOL_PLAN_ID
		);

		// Then
		assertThat(response.getToolPlanId()).isEqualTo(TOOL_PLAN_ID);
		assertThat(response.getToolPlanGroupId()).isEqualTo(TOOL_PLAN_GROUP_ID);
		assertThat(response.getPlanVersion()).isEqualTo(1L);
		assertThat(response.getRawMarkdown()).isEqualTo("raw");
		assertThat(response.getStructuredPlanJson()).isEqualTo("{\"version\":1,\"blocks\":[]}");
	}

	@Test
	@DisplayName("진행 중이 아닌 프로젝트 멤버는 ToolPlan 상세 정보를 조회할 수 없다.")
	void getToolPlanDetailFailWhenProjectMemberIsNotActive() {
		// Given
		ProjectMember completedMember = createProjectMember(project, user, ProjectMemberStatus.COMPLETED);
		when(userRepository.findById(USER_ID)).thenReturn(Optional.of(user));
		when(projectRepository.findById(PROJECT_ID)).thenReturn(Optional.of(project));
		when(projectMemberRepository.findByProjectAndUser(project, user)).thenReturn(Optional.of(completedMember));

		// When & Then
		assertThatThrownBy(() -> service.getToolPlanDetail(
			createAuthenticatedUser(),
			PROJECT_ID,
			SESSION_ID,
			TOOL_PLAN_ID
		))
			.isInstanceOf(BusinessException.class)
			.extracting("errorCode")
			.isEqualTo(ErrorCode.ACTIVE_PROJECT_MEMBER_REQUIRED);
	}

	private AuthenticatedUser createAuthenticatedUser() {
		return new AuthenticatedUser(USER_ID, "1000", "tester", SystemRole.USER);
	}

	private User createUser() {
		User createdUser = User.builder()
			.employeeNumber("1000")
			.name("tester")
			.email("tester@example.com")
			.password("password")
			.systemRole(SystemRole.USER)
			.build();
		ReflectionTestUtils.setField(createdUser, "id", USER_ID);
		return createdUser;
	}

	private Project createProject(User owner) {
		Project createdProject = Project.builder()
			.name("project")
			.createdByUser(owner)
			.projectAdminUser(owner)
			.build();
		ReflectionTestUtils.setField(createdProject, "id", PROJECT_ID);
		return createdProject;
	}

	private ProjectMember createProjectMember(Project project, User user, ProjectMemberStatus status) {
		ProjectMember createdProjectMember = ProjectMember.builder()
			.project(project)
			.user(user)
			.projectRole(ProjectRole.ADMIN)
			.status(status)
			.canCreateTool(true)
			.canUseTool(true)
			.canUpdateTool(true)
			.canDeleteTool(true)
			.build();
		ReflectionTestUtils.setField(createdProjectMember, "id", 10L);
		return createdProjectMember;
	}

	private ChatSession createChatSession(Project project, ProjectMember projectMember) {
		ChatSession createdChatSession = ChatSession.builder()
			.project(project)
			.projectMember(projectMember)
			.title("session")
			.build();
		ReflectionTestUtils.setField(createdChatSession, "id", SESSION_ID);
		return createdChatSession;
	}

	private ToolPlan createToolPlan(Project project, ProjectMember projectMember, ChatSession chatSession) {
		ToolPlanGroup planGroup = ToolPlanGroup.builder()
			.project(project)
			.chatSession(chatSession)
			.createdByProjectMember(projectMember)
			.status(ToolPlanGroupStatus.REVIEW)
			.build();
		ReflectionTestUtils.setField(planGroup, "id", TOOL_PLAN_GROUP_ID);

		ToolPlan createdToolPlan = ToolPlan.builder()
			.planGroup(planGroup)
			.project(project)
			.chatSession(chatSession)
			.createdByProjectMember(projectMember)
			.planVersion(1L)
			.status(ToolPlanStatus.REVIEW)
			.rawMarkdown("raw")
			.structuredPlanJson("{\"version\":1,\"blocks\":[]}")
			.planSnapshot("{}")
			.build();
		ReflectionTestUtils.setField(createdToolPlan, "id", TOOL_PLAN_ID);
		return createdToolPlan;
	}
}
