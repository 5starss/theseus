package com.theseus.api.domain.tool.entity;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.user.entity.User;
import java.time.LocalDateTime;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ToolPlanRunTest {

	@Test
	@DisplayName("ToolPlanRun 생성 시 기본 상태는 REQUESTED이다")
	void createToolPlanRunWithDefaultRequestedStatus() {
		// Given & When
		ToolPlanRun toolPlanRun = createToolPlanRun();

		// Then
		assertThat(toolPlanRun.getStatus()).isEqualTo(ToolPlanRunStatus.REQUESTED);
		assertThat(toolPlanRun.getMode()).isEqualTo(ToolPlanMode.PLAN);
		assertThat(toolPlanRun.isFinished()).isFalse();
	}

	@Test
	@DisplayName("ToolPlanRun 완료 시 result ToolPlan과 completedAt을 기록한다")
	void completeToolPlanRun() {
		// Given
		TestFixture fixture = createFixture();
		ToolPlanGroup planGroup = createToolPlanGroup(fixture);
		ToolPlan toolPlan = createToolPlan(fixture, planGroup);
		ToolPlanRun toolPlanRun = createToolPlanRun(fixture);
		LocalDateTime completedAt = LocalDateTime.of(2026, 5, 8, 14, 0);

		// When
		toolPlanRun.startGenerating();
		toolPlanRun.complete(toolPlan, completedAt);

		// Then
		assertThat(toolPlanRun.getStatus()).isEqualTo(ToolPlanRunStatus.COMPLETED);
		assertThat(toolPlanRun.getResultToolPlan()).isEqualTo(toolPlan);
		assertThat(toolPlanRun.getPlanGroup()).isEqualTo(planGroup);
		assertThat(toolPlanRun.getCompletedAt()).isEqualTo(completedAt);
		assertThat(toolPlanRun.isFinished()).isTrue();
	}

	@Test
	@DisplayName("ToolPlanRun 실패와 skipped 상태는 오류 정보를 기록한다")
	void finishToolPlanRunWithErrorMetadata() {
		// Given
		ToolPlanRun failedRun = createToolPlanRun();
		ToolPlanRun skippedRun = createToolPlanRun("run-skipped");
		LocalDateTime completedAt = LocalDateTime.of(2026, 5, 8, 14, 0);

		// When
		failedRun.fail("CORE_ERROR", "Core 처리 실패", completedAt);
		skippedRun.skip("NOT_TOOL_PLAN", "Tool 명세 요청이 아닙니다.", completedAt);

		// Then
		assertThat(failedRun.getStatus()).isEqualTo(ToolPlanRunStatus.FAILED);
		assertThat(failedRun.getErrorCode()).isEqualTo("CORE_ERROR");
		assertThat(skippedRun.getStatus()).isEqualTo(ToolPlanRunStatus.SKIPPED);
		assertThat(skippedRun.getErrorMessage()).isEqualTo("Tool 명세 요청이 아닙니다.");
	}

	@Test
	@DisplayName("종료된 ToolPlanRun은 다시 상태를 바꿀 수 없다")
	void cannotUpdateFinishedToolPlanRun() {
		// Given
		ToolPlanRun toolPlanRun = createToolPlanRun();
		toolPlanRun.fail("CORE_ERROR", "Core 처리 실패", LocalDateTime.of(2026, 5, 8, 14, 0));

		// When & Then
		assertThatThrownBy(toolPlanRun::startGenerating)
			.isInstanceOf(BusinessException.class);
	}

	@Test
	@DisplayName("runId가 비어 있으면 ToolPlanRun을 생성할 수 없다")
	void createToolPlanRunFailsWhenRunIdIsBlank() {
		// Given
		TestFixture fixture = createFixture();

		// When & Then
		assertThatThrownBy(() -> ToolPlanRun.builder()
			.runId(" ")
			.project(fixture.project())
			.chatSession(fixture.chatSession())
			.requestType(ToolPlanRunRequestType.GENERATE_PLAN)
			.requestedByProjectMember(fixture.projectMember())
			.build())
			.isInstanceOf(BusinessException.class);
	}

	private ToolPlanRun createToolPlanRun() {
		return createToolPlanRun("run-1");
	}

	private ToolPlanRun createToolPlanRun(String runId) {
		return createToolPlanRun(createFixture(), runId);
	}

	private ToolPlanRun createToolPlanRun(TestFixture fixture) {
		return createToolPlanRun(fixture, "run-1");
	}

	private ToolPlanRun createToolPlanRun(TestFixture fixture, String runId) {
		return ToolPlanRun.builder()
			.runId(runId)
			.project(fixture.project())
			.chatSession(fixture.chatSession())
			.requestType(ToolPlanRunRequestType.GENERATE_PLAN)
			.requestedByProjectMember(fixture.projectMember())
			.build();
	}

	private ToolPlanGroup createToolPlanGroup(TestFixture fixture) {
		return ToolPlanGroup.builder()
			.project(fixture.project())
			.chatSession(fixture.chatSession())
			.createdByProjectMember(fixture.projectMember())
			.build();
	}

	private ToolPlan createToolPlan(TestFixture fixture, ToolPlanGroup planGroup) {
		return ToolPlan.builder()
			.planGroup(planGroup)
			.project(fixture.project())
			.chatSession(fixture.chatSession())
			.createdByProjectMember(fixture.projectMember())
			.planVersion(1L)
			.rawMarkdown("raw markdown")
			.structuredPlanJson("{\"blocks\":[]}")
			.planSnapshot("{\"planVersion\":1}")
			.build();
	}

	private TestFixture createFixture() {
		Project project = createProject();
		ProjectMember projectMember = createProjectMember(project);
		ChatSession chatSession = createChatSession(project, projectMember);

		return new TestFixture(project, projectMember, chatSession);
	}

	private Project createProject() {
		User user = createUser("A001");

		return Project.builder()
			.name("Test Project")
			.createdByUser(user)
			.projectAdminUser(user)
			.build();
	}

	private ProjectMember createProjectMember(Project project) {
		return ProjectMember.builder()
			.project(project)
			.user(createUser("A002"))
			.projectRole(ProjectRole.ADMIN)
			.build();
	}

	private ChatSession createChatSession(Project project, ProjectMember projectMember) {
		return ChatSession.builder()
			.project(project)
			.projectMember(projectMember)
			.title("Test Session")
			.build();
	}

	private User createUser(String employeeNumber) {
		return User.builder()
			.employeeNumber(employeeNumber)
			.name("Test User")
			.password("encoded-password")
			.build();
	}

	private record TestFixture(Project project, ProjectMember projectMember, ChatSession chatSession) {
	}
}
