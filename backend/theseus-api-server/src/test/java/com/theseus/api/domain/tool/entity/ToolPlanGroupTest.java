package com.theseus.api.domain.tool.entity;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.user.entity.User;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ToolPlanGroupTest {

	@Test
	@DisplayName("ToolPlanGroup 생성 시 기본 상태는 PLANNING이다")
	void createToolPlanGroupWithDefaultPlanningStatus() {
		// Given & When
		TestFixture fixture = createFixture();
		ToolPlanGroup planGroup = createToolPlanGroup(fixture);

		// Then
		assertThat(planGroup.getStatus()).isEqualTo(ToolPlanGroupStatus.PLANNING);
		assertThat(planGroup.isFinished()).isFalse();
	}

	@Test
	@DisplayName("ToolPlanGroup은 최신 PLAN과 승인 PLAN 및 생성된 Tool을 순서대로 연결한다")
	void updateToolPlanGroupReferences() {
		// Given
		TestFixture fixture = createFixture();
		ToolPlanGroup planGroup = createToolPlanGroup(fixture);
		ToolPlan toolPlan = createToolPlan(fixture, planGroup);
		Tool tool = createTool(fixture, toolPlan);

		// When
		planGroup.markReview(toolPlan);
		planGroup.markPending(toolPlan);
		planGroup.approve(toolPlan);
		planGroup.startBuilding();
		planGroup.completeBuild(tool);

		// Then
		assertThat(planGroup.getLatestToolPlan()).isEqualTo(toolPlan);
		assertThat(planGroup.getApprovedToolPlan()).isEqualTo(toolPlan);
		assertThat(planGroup.getCreatedTool()).isEqualTo(tool);
		assertThat(planGroup.getStatus()).isEqualTo(ToolPlanGroupStatus.BUILT);
		assertThat(planGroup.isFinished()).isTrue();
	}

	@Test
	@DisplayName("APPROVED 상태가 아니면 Tool build를 시작할 수 없다")
	void startBuildingFailsWhenStatusIsNotApproved() {
		// Given
		ToolPlanGroup planGroup = createToolPlanGroup(createFixture());

		// When & Then
		assertThatThrownBy(planGroup::startBuilding)
			.isInstanceOf(BusinessException.class);
	}

	@Test
	@DisplayName("REVIEW 상태가 아니면 ToolPlanGroup을 PENDING으로 전환할 수 없다")
	void markPendingFailsWhenStatusIsNotReview() {
		// Given
		TestFixture fixture = createFixture();
		ToolPlanGroup planGroup = createToolPlanGroup(fixture);
		ToolPlan toolPlan = createToolPlan(fixture, planGroup);

		// When & Then
		assertThatThrownBy(() -> planGroup.markPending(toolPlan))
			.isInstanceOf(BusinessException.class);
	}

	@Test
	@DisplayName("PENDING 상태가 아니면 ToolPlanGroup을 승인할 수 없다")
	void approveFailsWhenStatusIsNotPending() {
		// Given
		TestFixture fixture = createFixture();
		ToolPlanGroup planGroup = createToolPlanGroup(fixture);
		ToolPlan toolPlan = createToolPlan(fixture, planGroup);
		planGroup.markReview(toolPlan);

		// When & Then
		assertThatThrownBy(() -> planGroup.approve(toolPlan))
			.isInstanceOf(BusinessException.class);
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

	private Tool createTool(TestFixture fixture, ToolPlan sourceToolPlan) {
		return Tool.builder()
			.project(fixture.project())
			.chatSession(fixture.chatSession())
			.createdByProjectMember(fixture.projectMember())
			.sourceToolPlan(sourceToolPlan)
			.fileName("incident-guide")
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
