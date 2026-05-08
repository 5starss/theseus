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

class ToolPlanTest {

	@Test
	@DisplayName("ToolPlan 생성 시 기본 상태는 REVIEW와 PLAN이다")
	void createToolPlanWithDefaultReviewStatusAndPlanMode() {
		// Given & When
		ToolPlan toolPlan = createToolPlan(1L);

		// Then
		assertThat(toolPlan.getStatus()).isEqualTo(ToolPlanStatus.REVIEW);
		assertThat(toolPlan.getMode()).isEqualTo(ToolPlanMode.PLAN);
		assertThat(toolPlan.canRegenerate()).isTrue();
	}

	@Test
	@DisplayName("ToolPlan은 승인 요청 후 승인 상태로 전환된다")
	void approveToolPlan() {
		// Given
		ToolPlan toolPlan = createToolPlan(1L);

		// When
		toolPlan.requestApproval();
		toolPlan.approve();

		// Then
		assertThat(toolPlan.getStatus()).isEqualTo(ToolPlanStatus.APPROVED);
		assertThat(toolPlan.canRegenerate()).isFalse();
	}

	@Test
	@DisplayName("ToolPlan은 REVIEW 또는 PENDING 상태에서 반려될 수 있다")
	void rejectToolPlan() {
		// Given
		ToolPlan toolPlan = createToolPlan(1L);

		// When
		toolPlan.reject();

		// Then
		assertThat(toolPlan.getStatus()).isEqualTo(ToolPlanStatus.REJECTED);
		assertThat(toolPlan.canRegenerate()).isTrue();
	}

	@Test
	@DisplayName("승인된 ToolPlan은 supersede 처리할 수 없다")
	void cannotSupersedeApprovedToolPlan() {
		// Given
		ToolPlan toolPlan = createToolPlan(1L);
		toolPlan.requestApproval();
		toolPlan.approve();

		// When & Then
		assertThatThrownBy(toolPlan::supersede)
			.isInstanceOf(BusinessException.class);
	}

	@Test
	@DisplayName("승인 요청 중인 ToolPlan은 supersede 처리할 수 없다")
	void cannotSupersedePendingToolPlan() {
		// Given
		ToolPlan toolPlan = createToolPlan(1L);
		toolPlan.requestApproval();

		// When & Then
		assertThatThrownBy(toolPlan::supersede)
			.isInstanceOf(BusinessException.class);
	}

	@Test
	@DisplayName("반려된 ToolPlan은 supersede 처리할 수 있다")
	void supersedeRejectedToolPlan() {
		// Given
		ToolPlan toolPlan = createToolPlan(1L);
		toolPlan.reject();

		// When
		toolPlan.supersede();

		// Then
		assertThat(toolPlan.getStatus()).isEqualTo(ToolPlanStatus.SUPERSEDED);
	}

	@Test
	@DisplayName("planVersion은 1 이상이어야 한다")
	void createToolPlanFailsWhenPlanVersionIsInvalid() {
		// When & Then
		assertThatThrownBy(() -> createToolPlan(0L))
			.isInstanceOf(BusinessException.class);
	}

	private ToolPlan createToolPlan(Long planVersion) {
		TestFixture fixture = createFixture();
		ToolPlanGroup planGroup = ToolPlanGroup.builder()
			.project(fixture.project())
			.chatSession(fixture.chatSession())
			.createdByProjectMember(fixture.projectMember())
			.build();

		return ToolPlan.builder()
			.planGroup(planGroup)
			.project(fixture.project())
			.chatSession(fixture.chatSession())
			.createdByProjectMember(fixture.projectMember())
			.planVersion(planVersion)
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
