package com.theseus.api.domain.toolgeneration.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.when;

import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.tool.entity.ToolPlanRun;
import com.theseus.api.domain.tool.entity.ToolPlanRunRequestType;
import com.theseus.api.domain.toolgeneration.dto.ToolPlanRunState;
import com.theseus.api.domain.toolgeneration.dto.response.ToolPlanRunStateResponse;
import com.theseus.api.domain.toolgeneration.redis.ToolPlanRunStateStore;
import com.theseus.api.domain.user.entity.SystemRole;
import com.theseus.api.domain.user.entity.User;
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
class ToolPlanRunStateServiceTest {

	private static final Long USER_ID = 10L;
	private static final Long PROJECT_ID = 20L;
	private static final Long CHAT_SESSION_ID = 30L;
	private static final String RUN_ID = "run-254";

	@Mock
	private ToolPlanRunAccessService toolPlanRunAccessService;

	@Mock
	private ToolPlanRunStateStore toolPlanRunStateStore;

	private ToolPlanRunStateService service;
	private ToolPlanRun toolPlanRun;

	@BeforeEach
	void setUp() {
		service = new ToolPlanRunStateService(toolPlanRunAccessService, toolPlanRunStateStore);
		toolPlanRun = createRun();
	}

	@Test
	@DisplayName("Redis에 ToolPlanRun 상태가 있으면 Redis 값을 우선 반환한다.")
	void getToolPlanRunStateFromRedis() {
		// Given
		when(toolPlanRunAccessService.getAccessibleRun(createAuthenticatedUser(), PROJECT_ID, CHAT_SESSION_ID, RUN_ID))
			.thenReturn(toolPlanRun);
		when(toolPlanRunStateStore.findByRunId(RUN_ID)).thenReturn(Optional.of(ToolPlanRunState.builder()
			.runId(RUN_ID)
			.projectId(PROJECT_ID)
			.chatSessionId(CHAT_SESSION_ID)
			.eventType("progress")
			.status("GENERATING")
			.progressRate(50)
			.updatedAt(LocalDateTime.of(2026, 5, 11, 10, 0))
			.build()));

		// When
		ToolPlanRunStateResponse response = service.getToolPlanRunState(
			createAuthenticatedUser(),
			PROJECT_ID,
			CHAT_SESSION_ID,
			RUN_ID
		);

		// Then
		assertThat(response.getEventType()).isEqualTo("progress");
		assertThat(response.getStatus()).isEqualTo("GENERATING");
		assertThat(response.getProgressRate()).isEqualTo(50);
	}

	@Test
	@DisplayName("Redis 상태가 없으면 ToolPlanRun DB 상태 기반 fallback을 반환한다.")
	void getToolPlanRunStateFallbackWhenRedisNotFound() {
		// Given
		when(toolPlanRunAccessService.getAccessibleRun(createAuthenticatedUser(), PROJECT_ID, CHAT_SESSION_ID, RUN_ID))
			.thenReturn(toolPlanRun);
		when(toolPlanRunStateStore.findByRunId(RUN_ID)).thenReturn(Optional.empty());

		// When
		ToolPlanRunStateResponse response = service.getToolPlanRunState(
			createAuthenticatedUser(),
			PROJECT_ID,
			CHAT_SESSION_ID,
			RUN_ID
		);

		// Then
		assertThat(response.getEventType()).isEqualTo("state");
		assertThat(response.getStatus()).isEqualTo("REQUESTED");
		assertThat(response.getRunId()).isEqualTo(RUN_ID);
	}

	@Test
	@DisplayName("Redis 조회 실패 시 ToolPlanRun DB 상태 기반 fallback을 반환한다.")
	void getToolPlanRunStateFallbackWhenRedisFails() {
		// Given
		when(toolPlanRunAccessService.getAccessibleRun(createAuthenticatedUser(), PROJECT_ID, CHAT_SESSION_ID, RUN_ID))
			.thenReturn(toolPlanRun);
		when(toolPlanRunStateStore.findByRunId(RUN_ID)).thenThrow(new IllegalStateException("redis error"));

		// When
		ToolPlanRunStateResponse response = service.getToolPlanRunState(
			createAuthenticatedUser(),
			PROJECT_ID,
			CHAT_SESSION_ID,
			RUN_ID
		);

		// Then
		assertThat(response.getEventType()).isEqualTo("state");
		assertThat(response.getStatus()).isEqualTo("REQUESTED");
	}

	private AuthenticatedUser createAuthenticatedUser() {
		return new AuthenticatedUser(USER_ID, "A254001", "Run State User", SystemRole.USER);
	}

	private ToolPlanRun createRun() {
		User user = User.builder()
			.employeeNumber("A254001")
			.name("Run State User")
			.password("encoded-password")
			.build();
		ReflectionTestUtils.setField(user, "id", USER_ID);

		Project project = Project.builder()
			.name("Run State Project")
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
			.title("Run State Session")
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
