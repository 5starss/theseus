package com.theseus.api.domain.tool.entity;

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

class ToolApprovalTest {

	@Test
	@DisplayName("ToolApproval defaults to PENDING")
	void createToolApprovalWithDefaultPendingStatus() {
		// Given & When
		ToolApproval toolApproval = createToolApproval();

		// Then
		assertThat(toolApproval.getApprovalStatus()).isEqualTo(ToolApprovalStatus.PENDING);
		assertThat(toolApproval.isPending()).isTrue();
		assertThat(toolApproval.isReviewed()).isFalse();
	}

	@Test
	@DisplayName("Approve ToolApproval records reviewer and review metadata")
	void approveToolApproval() {
		// Given
		ToolApproval toolApproval = createToolApproval();
		ProjectMember reviewer = createProjectMember(createProject(), "A003");
		LocalDateTime reviewedAt = LocalDateTime.of(2026, 4, 29, 10, 0);

		// When
		toolApproval.approve(reviewer, "approved", reviewedAt);

		// Then
		assertThat(toolApproval.getApprovalStatus()).isEqualTo(ToolApprovalStatus.APPROVED);
		assertThat(toolApproval.getReviewedByProjectMember()).isEqualTo(reviewer);
		assertThat(toolApproval.getReviewFeedback()).isEqualTo("approved");
		assertThat(toolApproval.getReviewedAt()).isEqualTo(reviewedAt);
		assertThat(toolApproval.isApproved()).isTrue();
		assertThat(toolApproval.isReviewed()).isTrue();
	}

	@Test
	@DisplayName("Reject ToolApproval records reviewer and feedback")
	void rejectToolApproval() {
		// Given
		ToolApproval toolApproval = createToolApproval();
		ProjectMember reviewer = createProjectMember(createProject(), "A003");
		LocalDateTime reviewedAt = LocalDateTime.of(2026, 4, 29, 10, 0);

		// When
		toolApproval.reject(reviewer, "needs revision", reviewedAt);

		// Then
		assertThat(toolApproval.getApprovalStatus()).isEqualTo(ToolApprovalStatus.REJECTED);
		assertThat(toolApproval.getReviewedByProjectMember()).isEqualTo(reviewer);
		assertThat(toolApproval.getReviewFeedback()).isEqualTo("needs revision");
		assertThat(toolApproval.getReviewedAt()).isEqualTo(reviewedAt);
		assertThat(toolApproval.isRejected()).isTrue();
		assertThat(toolApproval.isReviewed()).isTrue();
	}

	@Test
	@DisplayName("Reviewed ToolApproval cannot be reviewed again")
	void cannotReviewAlreadyReviewedToolApproval() {
		// Given
		ToolApproval toolApproval = createToolApproval();
		ProjectMember reviewer = createProjectMember(createProject(), "A003");
		toolApproval.approve(reviewer, "approved", LocalDateTime.of(2026, 4, 29, 10, 0));

		// When & Then
		assertThatThrownBy(() -> toolApproval.reject(reviewer, "reject", LocalDateTime.of(2026, 4, 29, 10, 1)))
			.isInstanceOf(IllegalStateException.class);
	}

	@Test
	@DisplayName("Request number must be greater than zero")
	void createToolApprovalFailsWhenRequestNumberIsInvalid() {
		// Given
		Project project = createProject();
		ProjectMember projectMember = createProjectMember(project, "A002");
		Tool tool = createTool(project, projectMember);

		// When & Then
		assertThatThrownBy(() -> ToolApproval.builder()
			.tool(tool)
			.requestNumber(0)
			.requestedByProjectMember(projectMember)
			.build())
			.isInstanceOf(IllegalArgumentException.class);
	}

	private ToolApproval createToolApproval() {
		Project project = createProject();
		ProjectMember projectMember = createProjectMember(project, "A002");
		Tool tool = createTool(project, projectMember);

		return ToolApproval.builder()
			.tool(tool)
			.requestNumber(1)
			.requestedByProjectMember(projectMember)
			.build();
	}

	private Tool createTool(Project project, ProjectMember projectMember) {
		ChatSession chatSession = ChatSession.builder()
			.project(project)
			.projectMember(projectMember)
			.title("Test Session")
			.build();

		return Tool.builder()
			.project(project)
			.chatSession(chatSession)
			.createdByProjectMember(projectMember)
			.fileName("sales-summary-tool")
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

	private ProjectMember createProjectMember(Project project, String employeeNumber) {
		return ProjectMember.builder()
			.project(project)
			.user(createUser(employeeNumber))
			.projectRole(ProjectRole.ADMIN)
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
