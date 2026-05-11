package com.theseus.api.domain.toolgeneration.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.same;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.theseus.api.domain.chat.entity.ChatMessageContentType;
import com.theseus.api.domain.chat.entity.ChatMessageSenderType;
import com.theseus.api.domain.chat.entity.ChatMessageType;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.chat.service.ChatMessageService;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.tool.entity.ToolPlan;
import com.theseus.api.domain.tool.entity.ToolPlanGroup;
import com.theseus.api.domain.tool.entity.ToolPlanGroupStatus;
import com.theseus.api.domain.tool.entity.ToolPlanRun;
import com.theseus.api.domain.tool.entity.ToolPlanRunRequestType;
import com.theseus.api.domain.tool.entity.ToolPlanRunStatus;
import com.theseus.api.domain.tool.repository.ToolPlanRunRepository;
import com.theseus.api.domain.toolgeneration.dto.ToolPlanRunState;
import com.theseus.api.domain.user.entity.User;
import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

@ExtendWith(MockitoExtension.class)
class ToolPlanRunRecoveryServiceTest {

	private static final Long PROJECT_ID = 10L;
	private static final Long CHAT_SESSION_ID = 30L;
	private static final String RUN_ID = "timeout-run-255";

	@Mock
	private ToolPlanRunRepository toolPlanRunRepository;

	@Mock
	private ChatMessageService chatMessageService;

	@Mock
	private ToolPlanRunStatePublisher toolPlanRunStatePublisher;

	private ToolPlanRunRecoveryService recoveryService;

	@BeforeEach
	void setUp() {
		recoveryService = new ToolPlanRunRecoveryService(
			toolPlanRunRepository,
			chatMessageService,
			toolPlanRunStatePublisher
		);
	}

	@Test
	@DisplayName("제한 시간을 넘긴 PLAN Run을 FAILED로 전환하고 System Notice와 failed 상태를 저장한다")
	void failTimedOutPlanRun() {
		// Given
		TestFixture fixture = createFixture();
		ToolPlanRun toolPlanRun = createRun(fixture, ToolPlanRunRequestType.GENERATE_PLAN, null, null);
		when(toolPlanRunRepository.findTimedOutRunsForUpdate(
			eq(List.of(ToolPlanRunStatus.REQUESTED, ToolPlanRunStatus.GENERATING)),
			any(LocalDateTime.class)
		)).thenReturn(List.of(toolPlanRun));

		// When
		int failedCount = recoveryService.failTimedOutRuns(Duration.ofMinutes(30));

		// Then
		assertThat(failedCount).isEqualTo(1);
		assertThat(toolPlanRun.getStatus()).isEqualTo(ToolPlanRunStatus.FAILED);
		assertThat(toolPlanRun.getErrorCode()).isEqualTo("TOOL_PLAN_RUN_TIMEOUT");
		verify(chatMessageService).saveToolPlanEventMessage(
			same(fixture.chatSession()),
			eq(null),
			same(toolPlanRun),
			eq(ChatMessageSenderType.SYSTEM),
			eq(ChatMessageType.SYSTEM_NOTICE),
			eq(ChatMessageContentType.TEXT),
			eq("ToolPlanRun 처리 시간이 초과되었습니다. code=TOOL_PLAN_RUN_TIMEOUT, message=ToolPlanRun 처리 시간이 초과되었습니다."),
			eq("tool-plan-run-timeout:timeout-run-255:system")
		);

		ArgumentCaptor<ToolPlanRunState> stateCaptor = ArgumentCaptor.forClass(ToolPlanRunState.class);
		verify(toolPlanRunStatePublisher).publishFailedAfterCommit(stateCaptor.capture());
		assertThat(stateCaptor.getValue().getRunId()).isEqualTo(RUN_ID);
		assertThat(stateCaptor.getValue().getStatus()).isEqualTo("FAILED");
		assertThat(stateCaptor.getValue().getErrorCode()).isEqualTo("TOOL_PLAN_RUN_TIMEOUT");
	}

	@Test
	@DisplayName("제한 시간을 넘긴 build Run은 PlanGroup도 FAILED로 전환한다")
	void failTimedOutBuildRun() {
		// Given
		TestFixture fixture = createFixture();
		ToolPlanGroup planGroup = createApprovedPlanGroup(fixture);
		ToolPlan toolPlan = planGroup.getApprovedToolPlan();
		ToolPlanRun buildRun = createRun(fixture, ToolPlanRunRequestType.BUILD_TOOL, planGroup, toolPlan);
		when(toolPlanRunRepository.findTimedOutRunsForUpdate(
			eq(List.of(ToolPlanRunStatus.REQUESTED, ToolPlanRunStatus.GENERATING)),
			any(LocalDateTime.class)
		)).thenReturn(List.of(buildRun));

		// When
		int failedCount = recoveryService.failTimedOutRuns(Duration.ofMinutes(30));

		// Then
		assertThat(failedCount).isEqualTo(1);
		assertThat(buildRun.getStatus()).isEqualTo(ToolPlanRunStatus.FAILED);
		assertThat(planGroup.getStatus()).isEqualTo(ToolPlanGroupStatus.FAILED);
		verify(chatMessageService).saveToolPlanEventMessage(
			same(fixture.chatSession()),
			same(toolPlan),
			same(buildRun),
			eq(ChatMessageSenderType.SYSTEM),
			eq(ChatMessageType.SYSTEM_NOTICE),
			eq(ChatMessageContentType.TEXT),
			any(String.class),
			eq("tool-plan-run-timeout:timeout-run-255:system")
		);
	}

	@Test
	@DisplayName("timeout 설정이 유효하지 않으면 Run을 조회하지 않는다")
	void skipInvalidTimeout() {
		// When
		int failedCount = recoveryService.failTimedOutRuns(Duration.ZERO);

		// Then
		assertThat(failedCount).isZero();
		verifyNoInteractions(toolPlanRunRepository, chatMessageService, toolPlanRunStatePublisher);
	}

	private ToolPlanRun createRun(
		TestFixture fixture,
		ToolPlanRunRequestType requestType,
		ToolPlanGroup planGroup,
		ToolPlan baseToolPlan
	) {
		return ToolPlanRun.builder()
			.runId(RUN_ID)
			.project(fixture.project())
			.chatSession(fixture.chatSession())
			.requestType(requestType)
			.requestedByProjectMember(fixture.projectMember())
			.planGroup(planGroup)
			.baseToolPlan(baseToolPlan)
			.requestedAt(LocalDateTime.of(2026, 5, 11, 12, 0))
			.build();
	}

	private ToolPlanGroup createApprovedPlanGroup(TestFixture fixture) {
		ToolPlanGroup planGroup = ToolPlanGroup.builder()
			.project(fixture.project())
			.chatSession(fixture.chatSession())
			.createdByProjectMember(fixture.projectMember())
			.build();
		ToolPlan toolPlan = ToolPlan.builder()
			.planGroup(planGroup)
			.project(fixture.project())
			.chatSession(fixture.chatSession())
			.createdByProjectMember(fixture.projectMember())
			.planVersion(1L)
			.rawMarkdown("## approved plan")
			.structuredPlanJson("{\"blocks\":[]}")
			.planSnapshot("{\"source\":\"test\"}")
			.build();
		ReflectionTestUtils.setField(toolPlan, "id", 50L);

		planGroup.markReview(toolPlan);
		toolPlan.requestApproval();
		planGroup.markPending(toolPlan);
		toolPlan.approve();
		planGroup.approve(toolPlan);
		return planGroup;
	}

	private TestFixture createFixture() {
		User user = User.builder()
			.employeeNumber("A255001")
			.name("Recovery User")
			.password("encoded-password")
			.build();
		ReflectionTestUtils.setField(user, "id", 1L);

		Project project = Project.builder()
			.name("Recovery Project")
			.createdByUser(user)
			.projectAdminUser(user)
			.build();
		ReflectionTestUtils.setField(project, "id", PROJECT_ID);

		ProjectMember projectMember = ProjectMember.builder()
			.project(project)
			.user(user)
			.projectRole(ProjectRole.ADMIN)
			.build();
		ReflectionTestUtils.setField(projectMember, "id", 20L);

		ChatSession chatSession = ChatSession.builder()
			.project(project)
			.projectMember(projectMember)
			.title("Recovery Session")
			.build();
		ReflectionTestUtils.setField(chatSession, "id", CHAT_SESSION_ID);

		return new TestFixture(project, projectMember, chatSession);
	}

	private record TestFixture(Project project, ProjectMember projectMember, ChatSession chatSession) {
	}
}
