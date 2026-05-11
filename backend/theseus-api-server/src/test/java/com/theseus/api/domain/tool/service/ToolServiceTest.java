package com.theseus.api.domain.tool.service;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.chat.repository.ChatSessionRepository;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.tool.dto.response.ToolDetailResponse;
import com.theseus.api.domain.tool.dto.response.ToolSummaryResponse;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolStatus;
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.domain.Page;
import org.springframework.transaction.annotation.Transactional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest
@Transactional
class ToolServiceTest {

	@Autowired
	private ToolService toolService;

	@Autowired
	private ToolRepository toolRepository;

	@Autowired
	private ChatSessionRepository chatSessionRepository;

	@Autowired
	private ProjectMemberRepository projectMemberRepository;

	@Autowired
	private ProjectRepository projectRepository;

	@Autowired
	private UserRepository userRepository;

	@Test
	@DisplayName("접근 가능한 승인 Tool 목록만 조회한다")
	void getToolsReturnsAccessibleApprovedTools() {
		// Given
		ProjectFixture fixture = createProjectFixture("A141001", 2, true);
		Tool accessibleGradeOneTool = createTool(fixture.project(), fixture.projectMember(), "grade-one", ToolStatus.APPROVED, 1);
		Tool accessibleGradeTwoTool = createTool(fixture.project(), fixture.projectMember(), "grade-two", ToolStatus.APPROVED, 2);
		createTool(fixture.project(), fixture.projectMember(), "grade-three", ToolStatus.APPROVED, 3);
		createTool(fixture.project(), fixture.projectMember(), "draft", ToolStatus.DRAFT, null);

		// When
		Page<ToolSummaryResponse> response = toolService.getTools(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			"accessible",
			ToolStatus.APPROVED,
			0,
			20
		);

		// Then
		assertThat(response.getTotalElements()).isEqualTo(2);
		assertThat(response.getContent())
			.extracting(ToolSummaryResponse::getToolId)
			.containsExactlyInAnyOrder(accessibleGradeOneTool.getId(), accessibleGradeTwoTool.getId());
		assertThat(response.getContent())
			.extracting(ToolSummaryResponse::getStatus)
			.containsOnly(ToolStatus.APPROVED);
	}

	@Test
	@DisplayName("접근 가능한 승인 Tool 상세 정보를 조회한다")
	void getToolReturnsAccessibleToolDetail() {
		// Given
		ProjectFixture fixture = createProjectFixture("A141011", 3, true);
		Tool tool = createTool(fixture.project(), fixture.projectMember(), "detail", ToolStatus.APPROVED, 3);

		// When
		ToolDetailResponse response = toolService.getTool(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			tool.getId()
		);

		// Then
		assertThat(response.getToolId()).isEqualTo(tool.getId());
		assertThat(response.getStatus()).isEqualTo(ToolStatus.APPROVED);
		assertThat(response.getToolGrade()).isEqualTo(3);
		assertThat(response.getModuleName()).isEqualTo("module-detail");
		assertThat(response.getArtifactPath()).isEqualTo("projects/tool-query-detail.py");
		assertThat(response.getCodeSnapshot()).isEqualTo("print('detail')");
		assertThat(response.getMetadataJson()).isEqualTo("{\"suffix\":\"detail\"}");
	}

	@Test
	@DisplayName("Tool 사용 권한이 없으면 Tool 목록을 조회할 수 없다")
	void getToolsFailsWhenCanUseToolIsFalse() {
		// Given
		ProjectFixture fixture = createProjectFixture("A141021", 3, false);
		createTool(fixture.project(), fixture.projectMember(), "blocked", ToolStatus.APPROVED, 1);

		// When & Then
		assertThatThrownBy(() -> toolService.getTools(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			"accessible",
			ToolStatus.APPROVED,
			0,
			20
		))
			.isInstanceOf(BusinessException.class)
			.extracting(exception -> ((BusinessException) exception).getErrorCode())
			.isEqualTo(ErrorCode.TOOL_USE_PERMISSION_REQUIRED);
	}

	@Test
	@DisplayName("접근 레벨이 Tool 등급보다 낮으면 Tool 상세를 조회할 수 없다")
	void getToolFailsWhenAccessLevelIsLowerThanToolGrade() {
		// Given
		ProjectFixture fixture = createProjectFixture("A141031", 1, true);
		Tool tool = createTool(fixture.project(), fixture.projectMember(), "high-grade", ToolStatus.APPROVED, 2);

		// When & Then
		assertThatThrownBy(() -> toolService.getTool(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			tool.getId()
		))
			.isInstanceOf(BusinessException.class)
			.extracting(exception -> ((BusinessException) exception).getErrorCode())
			.isEqualTo(ErrorCode.TOOL_ACCESS_LEVEL_REQUIRED);
	}

	@Test
	@DisplayName("지원하지 않는 조회 범위로 Tool 목록을 조회할 수 없다")
	void getToolsFailsWhenScopeIsUnsupported() {
		// Given
		ProjectFixture fixture = createProjectFixture("A141041", 3, true);

		// When & Then
		assertThatThrownBy(() -> toolService.getTools(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			"all",
			ToolStatus.APPROVED,
			0,
			20
		))
			.isInstanceOf(BusinessException.class)
			.extracting(exception -> ((BusinessException) exception).getErrorCode())
			.isEqualTo(ErrorCode.UNSUPPORTED_TOOL_SCOPE);
	}

	@Test
	@DisplayName("승인 상태가 아닌 Tool 목록은 조회할 수 없다")
	void getToolsFailsWhenStatusIsNotApproved() {
		// Given
		ProjectFixture fixture = createProjectFixture("A141051", 3, true);

		// When & Then
		assertThatThrownBy(() -> toolService.getTools(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			"accessible",
			ToolStatus.DRAFT,
			0,
			20
		))
			.isInstanceOf(BusinessException.class)
			.extracting(exception -> ((BusinessException) exception).getErrorCode())
			.isEqualTo(ErrorCode.APPROVED_TOOL_ONLY);
	}

	@Test
	@DisplayName("프로젝트 멤버가 아니면 Tool 상세를 조회할 수 없다")
	void getToolFailsWhenCurrentUserIsNotProjectMember() {
		// Given
		ProjectFixture fixture = createProjectFixture("A141061", 3, true);
		Tool tool = createTool(fixture.project(), fixture.projectMember(), "member-only", ToolStatus.APPROVED, 1);
		User outsider = createUser("A141062");

		// When & Then
		assertThatThrownBy(() -> toolService.getTool(
			createAuthenticatedUser(outsider),
			fixture.project().getId(),
			tool.getId()
		))
			.isInstanceOf(BusinessException.class)
			.extracting(exception -> ((BusinessException) exception).getErrorCode())
			.isEqualTo(ErrorCode.PROJECT_MEMBER_PERMISSION_REQUIRED);
	}

	private ProjectFixture createProjectFixture(String employeeNumber, Integer accessLevel, Boolean canUseTool) {
		User user = createUser(employeeNumber);
		Project project = projectRepository.save(Project.builder()
			.name("Tool Query Project " + employeeNumber)
			.createdByUser(user)
			.projectAdminUser(user)
			.build());
		ProjectMember projectMember = projectMemberRepository.save(ProjectMember.builder()
			.project(project)
			.user(user)
			.projectRole(ProjectRole.MEMBER)
			.accessLevel(accessLevel)
			.canUseTool(canUseTool)
			.build());

		return new ProjectFixture(user, project, projectMember);
	}

	private Tool createTool(
		Project project,
		ProjectMember projectMember,
		String suffix,
		ToolStatus status,
		Integer toolGrade
	) {
		ChatSession chatSession = chatSessionRepository.save(ChatSession.builder()
			.project(project)
			.projectMember(projectMember)
			.title("Tool Query Session " + suffix)
			.build());

		return toolRepository.save(Tool.builder()
			.project(project)
			.chatSession(chatSession)
			.createdByProjectMember(projectMember)
			.fileName("tool-query-" + suffix)
			.displayName("Tool " + suffix)
			.displayDescription("Tool query description " + suffix)
			.status(status)
			.toolGrade(toolGrade)
			.moduleName("module-" + suffix)
			.artifactPath("projects/tool-query-" + suffix + ".py")
			.codeSnapshot("print('" + suffix + "')")
			.metadataJson("{\"suffix\":\"" + suffix + "\"}")
			.build());
	}

	private User createUser(String employeeNumber) {
		return userRepository.save(User.builder()
			.employeeNumber(employeeNumber)
			.name("Tool Query User " + employeeNumber)
			.password("encoded-password")
			.build());
	}

	private AuthenticatedUser createAuthenticatedUser(User user) {
		return new AuthenticatedUser(
			user.getId(),
			user.getEmployeeNumber(),
			user.getName(),
			user.getSystemRole()
		);
	}

	private record ProjectFixture(
		User user,
		Project project,
		ProjectMember projectMember
	) {
	}
}
