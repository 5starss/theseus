package com.theseus.api.domain.tool.service;

import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.chat.repository.ChatSessionRepository;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.tool.dto.request.ToolApprovalApproveRequest;
import com.theseus.api.domain.tool.dto.request.ToolApprovalRejectRequest;
import com.theseus.api.domain.tool.dto.response.ToolApprovalResponse;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolApproval;
import com.theseus.api.domain.tool.entity.ToolApprovalStatus;
import com.theseus.api.domain.tool.entity.ToolDraftPhase;
import com.theseus.api.domain.tool.entity.ToolStatus;
import com.theseus.api.domain.tool.repository.ToolApprovalRepository;
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.http.HttpStatus;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

@SpringBootTest
@Transactional
class ToolApprovalServiceTest {

	@Autowired
	private ToolApprovalService toolApprovalService;

	@Autowired
	private ToolApprovalRepository toolApprovalRepository;

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
	@DisplayName("REVIEW 단계의 Draft Tool은 생성자가 승인 요청할 수 있다")
	void requestToolApproval() {
		// Given
		ProjectFixture fixture = createProjectFixture("A138001");
		Tool tool = createReviewPhaseDraftTool(fixture.project(), fixture.projectMember());

		// When
		ToolApprovalResponse response = toolApprovalService.requestToolApproval(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			tool.getId()
		);

		// Then
		Tool savedTool = toolRepository.findById(tool.getId()).orElseThrow();
		ToolApproval savedToolApproval = toolApprovalRepository.findById(response.getToolApprovalId()).orElseThrow();
		assertThat(response.getRequestNumber()).isEqualTo(1);
		assertThat(response.getApprovalStatus()).isEqualTo(ToolApprovalStatus.PENDING);
		assertThat(response.getToolStatus()).isEqualTo(ToolStatus.PENDING);
		assertThat(response.getDraftPhase()).isEqualTo(ToolDraftPhase.REVIEW);
		assertThat(response.getRequestedAt()).isNotNull();
		assertThat(savedTool.getStatus()).isEqualTo(ToolStatus.PENDING);
		assertThat(savedToolApproval.getRequestedByProjectMember().getId()).isEqualTo(fixture.projectMember().getId());
	}

	@Test
	@DisplayName("동일 Tool의 승인 요청 번호는 이전 요청 번호 다음 값으로 생성된다")
	void requestToolApprovalWithNextRequestNumber() {
		// Given
		ProjectFixture fixture = createProjectFixture("A138011");
		ProjectMember reviewer = createProjectMember(fixture.project(), createUser("A138012"), ProjectRole.ADMIN);
		Tool tool = createReviewPhaseDraftTool(fixture.project(), fixture.projectMember());
		ToolApproval previousApproval = toolApprovalRepository.save(ToolApproval.builder()
			.tool(tool)
			.requestNumber(1)
			.requestedByProjectMember(fixture.projectMember())
			.build());
		previousApproval.reject(reviewer, "needs revision");
		tool.reject();
		tool.startRegeneration();
		tool.completeDraftReview("raw markdown v2", "{\"steps\":[2]}", "{\"version\":2}");

		// When
		ToolApprovalResponse response = toolApprovalService.requestToolApproval(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			tool.getId()
		);

		// Then
		assertThat(response.getRequestNumber()).isEqualTo(2);
		assertThat(response.getApprovalStatus()).isEqualTo(ToolApprovalStatus.PENDING);
		assertThat(toolApprovalRepository.findByToolOrderByRequestNumberDesc(tool))
			.extracting(ToolApproval::getRequestNumber)
			.containsExactly(2, 1);
	}

	@Test
	@DisplayName("Tool 생성자가 아니면 승인 요청할 수 없다")
	void requestToolApprovalFailsWhenCurrentUserIsNotToolCreator() {
		// Given
		ProjectFixture creatorFixture = createProjectFixture("A138021");
		User otherUser = createUser("A138022");
		ProjectMember otherProjectMember = createProjectMember(creatorFixture.project(), otherUser, ProjectRole.MEMBER);
		Tool tool = createReviewPhaseDraftTool(creatorFixture.project(), creatorFixture.projectMember());

		// When & Then
		assertThatThrownBy(() -> toolApprovalService.requestToolApproval(
			createAuthenticatedUser(otherProjectMember.getUser()),
			creatorFixture.project().getId(),
			tool.getId()
		))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(exception -> ((ResponseStatusException) exception).getStatusCode())
			.isEqualTo(HttpStatus.FORBIDDEN);
	}

	@Test
	@DisplayName("REVIEW 단계가 아닌 Draft Tool은 승인 요청할 수 없다")
	void requestToolApprovalFailsWhenDraftPhaseIsNotReview() {
		// Given
		ProjectFixture fixture = createProjectFixture("A138031");
		Tool tool = createDraftTool(fixture.project(), fixture.projectMember());

		// When & Then
		assertThatThrownBy(() -> toolApprovalService.requestToolApproval(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			tool.getId()
		))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(exception -> ((ResponseStatusException) exception).getStatusCode())
			.isEqualTo(HttpStatus.CONFLICT);
	}

	@Test
	@DisplayName("Project ADMIN can approve pending ToolApproval")
	void approveToolApproval() {
		// Given
		ProjectFixture fixture = createProjectFixture("A140001");
		ToolApproval toolApproval = createPendingToolApproval(fixture);

		// When
		ToolApprovalResponse response = toolApprovalService.approveToolApproval(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			toolApproval.getId(),
			createApproveRequest(3, "approved")
		);

		// Then
		Tool savedTool = toolRepository.findById(response.getToolId()).orElseThrow();
		ToolApproval savedToolApproval = toolApprovalRepository.findById(response.getToolApprovalId()).orElseThrow();
		assertThat(response.getApprovalStatus()).isEqualTo(ToolApprovalStatus.APPROVED);
		assertThat(response.getToolStatus()).isEqualTo(ToolStatus.APPROVED);
		assertThat(response.getReviewedByProjectMemberId()).isEqualTo(fixture.projectMember().getId());
		assertThat(response.getReviewFeedback()).isEqualTo("approved");
		assertThat(response.getReviewedAt()).isNotNull();
		assertThat(savedTool.getStatus()).isEqualTo(ToolStatus.APPROVED);
		assertThat(savedTool.getToolGrade()).isEqualTo(3);
		assertThat(savedToolApproval.getReviewedByProjectMember().getId()).isEqualTo(fixture.projectMember().getId());
	}

	@Test
	@DisplayName("Project MANAGER can reject pending ToolApproval")
	void rejectToolApproval() {
		// Given
		ProjectFixture creatorFixture = createProjectFixture("A140011");
		User managerUser = createUser("A140012");
		ProjectMember manager = createProjectMember(creatorFixture.project(), managerUser, ProjectRole.MANAGER);
		ToolApproval toolApproval = createPendingToolApproval(creatorFixture);

		// When
		ToolApprovalResponse response = toolApprovalService.rejectToolApproval(
			createAuthenticatedUser(managerUser),
			creatorFixture.project().getId(),
			toolApproval.getId(),
			createRejectRequest("needs revision")
		);

		// Then
		Tool savedTool = toolRepository.findById(response.getToolId()).orElseThrow();
		assertThat(response.getApprovalStatus()).isEqualTo(ToolApprovalStatus.REJECTED);
		assertThat(response.getToolStatus()).isEqualTo(ToolStatus.REJECTED);
		assertThat(response.getDraftPhase()).isEqualTo(ToolDraftPhase.REVIEW);
		assertThat(response.getReviewedByProjectMemberId()).isEqualTo(manager.getId());
		assertThat(response.getReviewFeedback()).isEqualTo("needs revision");
		assertThat(response.getReviewedAt()).isNotNull();
		assertThat(savedTool.getStatus()).isEqualTo(ToolStatus.REJECTED);
		assertThat(savedTool.getDraftPhase()).isEqualTo(ToolDraftPhase.REVIEW);
	}

	@Test
	@DisplayName("Project MEMBER cannot approve ToolApproval")
	void approveToolApprovalFailsWhenReviewerIsMember() {
		// Given
		ProjectFixture creatorFixture = createProjectFixture("A140021");
		User memberUser = createUser("A140022");
		createProjectMember(creatorFixture.project(), memberUser, ProjectRole.MEMBER);
		ToolApproval toolApproval = createPendingToolApproval(creatorFixture);

		// When & Then
		assertThatThrownBy(() -> toolApprovalService.approveToolApproval(
			createAuthenticatedUser(memberUser),
			creatorFixture.project().getId(),
			toolApproval.getId(),
			createApproveRequest(2, "approved")
		))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(exception -> ((ResponseStatusException) exception).getStatusCode())
			.isEqualTo(HttpStatus.FORBIDDEN);
	}

	@Test
	@DisplayName("Reviewed ToolApproval cannot be rejected again")
	void rejectToolApprovalFailsWhenAlreadyReviewed() {
		// Given
		ProjectFixture fixture = createProjectFixture("A140031");
		ToolApproval toolApproval = createPendingToolApproval(fixture);
		toolApprovalService.approveToolApproval(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			toolApproval.getId(),
			createApproveRequest(3, "approved")
		);

		// When & Then
		assertThatThrownBy(() -> toolApprovalService.rejectToolApproval(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			toolApproval.getId(),
			createRejectRequest("reject")
		))
			.isInstanceOf(ResponseStatusException.class)
			.extracting(exception -> ((ResponseStatusException) exception).getStatusCode())
			.isEqualTo(HttpStatus.CONFLICT);
	}

	private ToolApproval createPendingToolApproval(ProjectFixture fixture) {
		Tool tool = createReviewPhaseDraftTool(fixture.project(), fixture.projectMember());
		ToolApprovalResponse response = toolApprovalService.requestToolApproval(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			tool.getId()
		);

		return toolApprovalRepository.findById(response.getToolApprovalId()).orElseThrow();
	}

	private Tool createReviewPhaseDraftTool(Project project, ProjectMember projectMember) {
		Tool tool = createDraftTool(project, projectMember);
		tool.completeDraftReview("raw markdown", "{\"steps\":[1]}", "{\"version\":1}");

		return tool;
	}

	private Tool createDraftTool(Project project, ProjectMember projectMember) {
		ChatSession chatSession = chatSessionRepository.save(ChatSession.builder()
			.project(project)
			.projectMember(projectMember)
			.title("Tool Session")
			.build());

		return toolRepository.save(Tool.builder()
			.project(project)
			.chatSession(chatSession)
			.createdByProjectMember(projectMember)
			.fileName("tool-" + projectMember.getUser().getEmployeeNumber())
			.build());
	}

	private ProjectFixture createProjectFixture(String employeeNumber) {
		User user = createUser(employeeNumber);
		Project project = projectRepository.save(Project.builder()
			.name("Test Project " + employeeNumber)
			.createdByUser(user)
			.projectAdminUser(user)
			.build());
		ProjectMember projectMember = createProjectMember(project, user, ProjectRole.ADMIN);

		return new ProjectFixture(user, project, projectMember);
	}

	private ProjectMember createProjectMember(Project project, User user, ProjectRole projectRole) {
		return projectMemberRepository.save(ProjectMember.builder()
			.project(project)
			.user(user)
			.projectRole(projectRole)
			.canCreateTool(true)
			.canUseTool(true)
			.canUpdateTool(true)
			.canDeleteTool(true)
			.build());
	}

	private User createUser(String employeeNumber) {
		return userRepository.save(User.builder()
			.employeeNumber(employeeNumber)
			.name("Test User " + employeeNumber)
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

	private ToolApprovalApproveRequest createApproveRequest(Integer toolGrade, String reviewFeedback) {
		ToolApprovalApproveRequest request = new ToolApprovalApproveRequest();
		ReflectionTestUtils.setField(request, "toolGrade", toolGrade);
		ReflectionTestUtils.setField(request, "reviewFeedback", reviewFeedback);

		return request;
	}

	private ToolApprovalRejectRequest createRejectRequest(String reviewFeedback) {
		ToolApprovalRejectRequest request = new ToolApprovalRejectRequest();
		ReflectionTestUtils.setField(request, "reviewFeedback", reviewFeedback);

		return request;
	}

	private record ProjectFixture(
		User user,
		Project project,
		ProjectMember projectMember
	) {
	}
}
