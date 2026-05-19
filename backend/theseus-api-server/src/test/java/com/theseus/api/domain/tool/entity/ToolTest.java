package com.theseus.api.domain.tool.entity;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.user.entity.User;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

class ToolTest {

	@Test
	@DisplayName("Tool is approved by default after artifact creation")
	void createToolWithDefaultApprovedStatus() {
		// Given & When
		Tool tool = createTool(null);

		// Then
		assertThat(tool.getStatus()).isEqualTo(ToolStatus.APPROVED);
		assertThat(tool.isApproved()).isTrue();
	}

	@Test
	@DisplayName("Tool keeps source plan and artifact metadata")
	void createToolWithSourcePlanAndArtifact() {
		// Given
		ToolPlan sourceToolPlan = createToolPlan();

		// When
		Tool tool = createTool(null, sourceToolPlan);

		// Then
		assertThat(tool.getSourceToolPlan()).isEqualTo(sourceToolPlan);
		assertThat(tool.getModuleName()).isEqualTo("sales_summary");
		assertThat(tool.getArtifactPath()).isEqualTo("projects/1/sales_summary.py");
		assertThat(tool.getCodeSnapshot()).isEqualTo("print('ok')");
		assertThat(tool.getMetadataJson()).isEqualTo("{\"language\":\"python\"}");
	}

	@Test
	@DisplayName("Tool artifact metadata can be updated")
	void updateArtifactChangesStoredMetadata() {
		// Given
		Tool tool = createTool(null);

		// When
		tool.updateArtifact(
			"incident_recovery",
			"projects/1/incident_recovery.py",
			"print('updated')",
			"{\"language\":\"python\",\"version\":2}"
		);

		// Then
		assertThat(tool.getModuleName()).isEqualTo("incident_recovery");
		assertThat(tool.getArtifactPath()).isEqualTo("projects/1/incident_recovery.py");
		assertThat(tool.getCodeSnapshot()).isEqualTo("print('updated')");
		assertThat(tool.getMetadataJson()).isEqualTo("{\"language\":\"python\",\"version\":2}");
	}

	@Test
	@DisplayName("Tool display fields can be updated")
	void updateDisplayInfoChangesDisplayFields() {
		// Given
		Tool tool = createTool(null);

		// When
		tool.updateDisplayInfo("Incident Recovery", "Builds recovery guide.", 3);

		// Then
		assertThat(tool.getDisplayName()).isEqualTo("Incident Recovery");
		assertThat(tool.getDisplayDescription()).isEqualTo("Builds recovery guide.");
		assertThat(tool.getToolGrade()).isEqualTo(3);
	}

	@Test
	@DisplayName("Tool is accessible when grade is empty")
	void accessibleWhenToolGradeIsNull() {
		// Given
		Tool tool = createTool(null);

		// When & Then
		assertThat(tool.isAccessibleWithAccessLevel(null)).isTrue();
		assertThat(tool.isAccessibleWithAccessLevel(1)).isTrue();
	}

	@Test
	@DisplayName("Tool requires access level greater than or equal to grade")
	void accessibleWhenAccessLevelIsGreaterThanOrEqualToToolGrade() {
		// Given
		Tool tool = createTool(3);

		// When & Then
		assertThat(tool.isAccessibleWithAccessLevel(null)).isFalse();
		assertThat(tool.isAccessibleWithAccessLevel(2)).isFalse();
		assertThat(tool.isAccessibleWithAccessLevel(3)).isTrue();
		assertThat(tool.isAccessibleWithAccessLevel(4)).isTrue();
	}

	@Test
	@DisplayName("Tool can be deleted")
	void deleteChangesStatusToDeleted() {
		// Given
		Tool tool = createTool(null);
		ReflectionTestUtils.setField(tool, "id", 7L);

		// When
		tool.delete();

		// Then
		assertThat(tool.getStatus()).isEqualTo(ToolStatus.DELETED);
		assertThat(tool.isDeleted()).isTrue();
		assertThat(tool.getFileName()).isEqualTo("deleted_7_sales-summary-tool");
	}

	@Test
	@DisplayName("Tool cannot be created with blank fileName")
	void createToolFailsWhenFileNameIsBlank() {
		// Given
		Project project = createProject();
		ProjectMember projectMember = createProjectMember(project);
		ChatSession chatSession = createChatSession(project, projectMember);

		// When & Then
		assertThatThrownBy(() -> Tool.builder()
			.project(project)
			.chatSession(chatSession)
			.createdByProjectMember(projectMember)
			.fileName(" ")
			.build())
			.isInstanceOf(BusinessException.class);
	}

	private Tool createTool(Integer toolGrade) {
		return createTool(toolGrade, null);
	}

	private Tool createTool(Integer toolGrade, ToolPlan sourceToolPlan) {
		Project project = createProject();
		ProjectMember projectMember = createProjectMember(project);
		ChatSession chatSession = createChatSession(project, projectMember);

		return Tool.builder()
			.project(project)
			.chatSession(chatSession)
			.createdByProjectMember(projectMember)
			.sourceToolPlan(sourceToolPlan)
			.fileName("sales-summary-tool")
			.displayName("Sales Summary")
			.displayDescription("Summarizes sales data.")
			.toolGrade(toolGrade)
			.moduleName("sales_summary")
			.artifactPath("projects/1/sales_summary.py")
			.codeSnapshot("print('ok')")
			.metadataJson("{\"language\":\"python\"}")
			.build();
	}

	private ToolPlan createToolPlan() {
		Project project = createProject();
		ProjectMember projectMember = createProjectMember(project);
		ChatSession chatSession = createChatSession(project, projectMember);
		ToolPlanGroup planGroup = ToolPlanGroup.builder()
			.project(project)
			.chatSession(chatSession)
			.createdByProjectMember(projectMember)
			.build();

		return ToolPlan.builder()
			.planGroup(planGroup)
			.project(project)
			.chatSession(chatSession)
			.createdByProjectMember(projectMember)
			.planVersion(1L)
			.rawMarkdown("## plan")
			.structuredPlanJson("{\"blocks\":[]}")
			.planSnapshot("{\"source\":\"test\"}")
			.build();
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
}
