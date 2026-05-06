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

class ToolTest {

	@Test
	@DisplayName("Tool 생성 시 기본 상태는 DRAFT와 PLAN이다")
	void createToolWithDefaultStatusAndDraftPhase() {
		// Given & When
		Tool tool = createTool(null);

		// Then
		assertThat(tool.getStatus()).isEqualTo(ToolStatus.DRAFT);
		assertThat(tool.getDraftPhase()).isEqualTo(ToolDraftPhase.PLAN);
		assertThat(tool.canRegenerate()).isTrue();
		assertThat(tool.canRequestApproval()).isFalse();
	}

	@Test
	@DisplayName("Tool 초안 검토 완료 시 draft 데이터와 REVIEW 상태를 반영한다")
	void completeDraftReviewUpdatesDraftDataAndPhase() {
		// Given
		Tool tool = createTool(null);

		// When
		tool.completeDraftReview("raw markdown", "{\"steps\":[]}", "{\"version\":1}");

		// Then
		assertThat(tool.getRawMarkdown()).isEqualTo("raw markdown");
		assertThat(tool.getStructuredPlanJson()).isEqualTo("{\"steps\":[]}");
		assertThat(tool.getDraftSnapshot()).isEqualTo("{\"version\":1}");
		assertThat(tool.getDraftPhase()).isEqualTo(ToolDraftPhase.REVIEW);
		assertThat(tool.canRequestApproval()).isTrue();
	}

	@Test
	@DisplayName("반려된 Tool은 재생성을 시작하면 DRAFT와 PLAN 상태가 된다")
	void startRegenerationChangesRejectedToolToDraftPlan() {
		// Given
		Tool tool = createTool(null);
		tool.reject();

		// When
		tool.startRegeneration();

		// Then
		assertThat(tool.getStatus()).isEqualTo(ToolStatus.DRAFT);
		assertThat(tool.getDraftPhase()).isEqualTo(ToolDraftPhase.PLAN);
	}

	@Test
	@DisplayName("Tool 등급이 없으면 모든 접근 레벨에서 접근할 수 있다")
	void accessibleWhenToolGradeIsNull() {
		// Given
		Tool tool = createTool(null);

		// When & Then
		assertThat(tool.isAccessibleWithAccessLevel(null)).isTrue();
		assertThat(tool.isAccessibleWithAccessLevel(1)).isTrue();
	}

	@Test
	@DisplayName("Tool 등급이 있으면 접근 레벨이 등급 이상이어야 한다")
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
	@DisplayName("fileName이 비어 있으면 Tool을 생성할 수 없다")
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
		Project project = createProject();
		ProjectMember projectMember = createProjectMember(project);
		ChatSession chatSession = createChatSession(project, projectMember);

		return Tool.builder()
			.project(project)
			.chatSession(chatSession)
			.createdByProjectMember(projectMember)
			.fileName("sales-summary-tool")
			.toolGrade(toolGrade)
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
