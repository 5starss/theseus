package com.theseus.api.domain.tool.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.entity.ChatMessage;
import com.theseus.api.domain.chat.entity.ChatMessageType;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.chat.repository.ChatMessageRepository;
import com.theseus.api.domain.chat.repository.ChatSessionRepository;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.tool.dto.request.ToolApprovalApproveRequest;
import com.theseus.api.domain.tool.dto.request.ToolApprovalRejectRequest;
import com.theseus.api.domain.tool.dto.response.ToolApprovalResponse;
import com.theseus.api.domain.tool.entity.ToolApproval;
import com.theseus.api.domain.tool.entity.ToolPlan;
import com.theseus.api.domain.tool.entity.ToolPlanGroup;
import com.theseus.api.domain.tool.entity.ToolPlanGroupStatus;
import com.theseus.api.domain.tool.entity.ToolPlanRun;
import com.theseus.api.domain.tool.entity.ToolPlanRunRequestType;
import com.theseus.api.domain.tool.entity.ToolPlanRunStatus;
import com.theseus.api.domain.tool.entity.ToolPlanStatus;
import com.theseus.api.domain.tool.repository.ToolApprovalRepository;
import com.theseus.api.domain.tool.repository.ToolPlanGroupRepository;
import com.theseus.api.domain.tool.repository.ToolPlanRepository;
import com.theseus.api.domain.tool.repository.ToolPlanRunRepository;
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.annotation.Transactional;

@SpringBootTest
@Transactional
class ToolApprovalServiceTest {

	@Autowired
	private ToolApprovalService toolApprovalService;

	@Autowired
	private ToolApprovalRepository toolApprovalRepository;

	@Autowired
	private ToolPlanRepository toolPlanRepository;

	@Autowired
	private ToolPlanGroupRepository toolPlanGroupRepository;

	@Autowired
	private ToolPlanRunRepository toolPlanRunRepository;

	@Autowired
	private ToolRepository toolRepository;

	@Autowired
	private ChatSessionRepository chatSessionRepository;

	@Autowired
	private ChatMessageRepository chatMessageRepository;

	@Autowired
	private ProjectMemberRepository projectMemberRepository;

	@Autowired
	private ProjectRepository projectRepository;

	@Autowired
	private UserRepository userRepository;

	@Test
	@DisplayName("REVIEW ToolPlan can be requested for approval by its creator")
	void requestToolPlanApproval() {
		// Given
		ProjectFixture fixture = createProjectFixture("A252101", ProjectRole.MEMBER);
		ToolPlan toolPlan = createReviewToolPlan(fixture);

		// When
		ToolApprovalResponse response = toolApprovalService.requestToolPlanApproval(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			toolPlan.getId()
		);

		// Then
		ToolApproval savedToolApproval = toolApprovalRepository.findById(response.getToolApprovalId()).orElseThrow();
		ToolPlan savedToolPlan = toolPlanRepository.findById(toolPlan.getId()).orElseThrow();
		ChatMessage savedMessage = chatMessageRepository.findByToolPlanOrderByMessageOrderAsc(savedToolPlan).getFirst();

		assertThat(response.getToolPlanId()).isEqualTo(toolPlan.getId());
		assertThat(response.getChatSessionId()).isEqualTo(toolPlan.getChatSession().getId());
		assertThat(response.getToolId()).isNull();
		assertThat(response.getToolPlanStatus()).isEqualTo(ToolPlanStatus.PENDING);
		assertThat(savedToolApproval.getTool()).isNull();
		assertThat(savedToolApproval.getToolPlan().getId()).isEqualTo(toolPlan.getId());
		assertThat(savedToolPlan.getStatus()).isEqualTo(ToolPlanStatus.PENDING);
		assertThat(savedToolPlan.getPlanGroup().getStatus()).isEqualTo(ToolPlanGroupStatus.PENDING);
		assertThat(savedMessage.getMessageType()).isEqualTo(ChatMessageType.TOOL_APPROVAL_REQUEST);
	}

	@Test
	@DisplayName("ToolPlan approval request fails when ToolPlan is not REVIEW")
	void requestToolPlanApprovalFailsWhenPlanIsNotReview() {
		// Given
		ProjectFixture fixture = createProjectFixture("A252102", ProjectRole.MEMBER);
		ToolPlan toolPlan = createReviewToolPlan(fixture);
		toolPlan.requestApproval();
		toolPlan.getPlanGroup().markPending(toolPlan);

		// When & Then
		assertThatThrownBy(() -> toolApprovalService.requestToolPlanApproval(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			toolPlan.getId()
		))
			.isInstanceOf(BusinessException.class)
			.extracting(exception -> ((BusinessException) exception).getErrorCode())
			.isEqualTo(ErrorCode.TOOL_PLAN_APPROVAL_REVIEW_STATUS_REQUIRED);
	}

	@Test
	@DisplayName("Approving ToolPlan creates build run and does not create Tool row")
	void approveToolPlanApprovalCreatesBuildRunWithoutTool() {
		// Given
		ProjectFixture fixture = createProjectFixture("A252103", ProjectRole.MEMBER);
		ProjectMember reviewer = createProjectMember(fixture.project(), createUser("A252104"), ProjectRole.ADMIN);
		ToolApproval toolApproval = createPendingToolPlanApproval(fixture);
		ToolPlan toolPlan = toolApproval.getToolPlan();
		ToolApprovalApproveRequest request = new ToolApprovalApproveRequest();
		ReflectionTestUtils.setField(request, "toolGrade", 3);
		ReflectionTestUtils.setField(request, "reviewFeedback", "approve");

		// When
		ToolApprovalResponse response = toolApprovalService.approveToolApproval(
			createAuthenticatedUser(reviewer.getUser()),
			fixture.project().getId(),
			toolApproval.getId(),
			request
		);

		// Then
		ToolPlan savedToolPlan = toolPlanRepository.findById(toolPlan.getId()).orElseThrow();
		ToolPlanGroup savedPlanGroup = toolPlanGroupRepository.findById(savedToolPlan.getPlanGroup().getId())
			.orElseThrow();
		ToolPlanRun savedBuildRun = toolPlanRunRepository.findByProjectAndChatSessionAndStatusOrderByRequestedAtDesc(
			fixture.project(),
			savedToolPlan.getChatSession(),
			ToolPlanRunStatus.REQUESTED
		).getFirst();

		assertThat(response.getToolPlanId()).isEqualTo(toolPlan.getId());
		assertThat(response.getToolId()).isNull();
		assertThat(response.getToolPlanStatus()).isEqualTo(ToolPlanStatus.APPROVED);
		assertThat(savedToolPlan.getStatus()).isEqualTo(ToolPlanStatus.APPROVED);
		assertThat(savedPlanGroup.getStatus()).isEqualTo(ToolPlanGroupStatus.APPROVED);
		assertThat(savedBuildRun.getRequestType()).isEqualTo(ToolPlanRunRequestType.BUILD_TOOL);
		assertThat(savedBuildRun.getBaseToolPlan().getId()).isEqualTo(toolPlan.getId());
		assertThat(toolRepository.findBySourceToolPlan(savedToolPlan)).isEmpty();
	}

	@Test
	@DisplayName("Rejecting ToolPlan approval changes ToolPlan and group to REJECTED")
	void rejectToolPlanApproval() {
		// Given
		ProjectFixture fixture = createProjectFixture("A252105", ProjectRole.MEMBER);
		ProjectMember reviewer = createProjectMember(fixture.project(), createUser("A252106"), ProjectRole.ADMIN);
		ToolApproval toolApproval = createPendingToolPlanApproval(fixture);
		ToolPlan toolPlan = toolApproval.getToolPlan();
		ToolApprovalRejectRequest request = new ToolApprovalRejectRequest();
		ReflectionTestUtils.setField(request, "reviewFeedback", "reject");

		// When
		ToolApprovalResponse response = toolApprovalService.rejectToolApproval(
			createAuthenticatedUser(reviewer.getUser()),
			fixture.project().getId(),
			toolApproval.getId(),
			request
		);

		// Then
		ToolPlan savedToolPlan = toolPlanRepository.findById(toolPlan.getId()).orElseThrow();
		ToolPlanGroup savedPlanGroup = toolPlanGroupRepository.findById(savedToolPlan.getPlanGroup().getId())
			.orElseThrow();
		ChatMessage savedNotice = chatMessageRepository.findByToolPlanOrderByMessageOrderAsc(savedToolPlan)
			.getLast();

		assertThat(response.getToolPlanId()).isEqualTo(toolPlan.getId());
		assertThat(response.getToolId()).isNull();
		assertThat(response.getToolPlanStatus()).isEqualTo(ToolPlanStatus.REJECTED);
		assertThat(savedToolPlan.getStatus()).isEqualTo(ToolPlanStatus.REJECTED);
		assertThat(savedPlanGroup.getStatus()).isEqualTo(ToolPlanGroupStatus.REJECTED);
		assertThat(savedNotice.getMessageType()).isEqualTo(ChatMessageType.SYSTEM_NOTICE);
		assertThat(toolRepository.findBySourceToolPlan(savedToolPlan)).isEmpty();
	}

	private ToolApproval createPendingToolPlanApproval(ProjectFixture fixture) {
		ToolPlan toolPlan = createReviewToolPlan(fixture);
		ToolApprovalResponse response = toolApprovalService.requestToolPlanApproval(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			toolPlan.getId()
		);

		return toolApprovalRepository.findById(response.getToolApprovalId()).orElseThrow();
	}

	private ToolPlan createReviewToolPlan(ProjectFixture fixture) {
		ChatSession chatSession = chatSessionRepository.save(ChatSession.builder()
			.project(fixture.project())
			.projectMember(fixture.projectMember())
			.title("ToolPlan Session " + fixture.user().getEmployeeNumber())
			.build());
		ToolPlanGroup planGroup = toolPlanGroupRepository.save(ToolPlanGroup.builder()
			.project(fixture.project())
			.chatSession(chatSession)
			.createdByProjectMember(fixture.projectMember())
			.build());
		ToolPlan toolPlan = toolPlanRepository.save(ToolPlan.builder()
			.planGroup(planGroup)
			.project(fixture.project())
			.chatSession(chatSession)
			.createdByProjectMember(fixture.projectMember())
			.planVersion(1L)
			.status(ToolPlanStatus.REVIEW)
			.rawMarkdown("## plan")
			.structuredPlanJson("{\"blocks\":[]}")
			.planSnapshot("{\"source\":\"test\"}")
			.build());
		planGroup.markReview(toolPlan);
		return toolPlan;
	}

	private ProjectFixture createProjectFixture(String employeeNumber, ProjectRole projectRole) {
		User user = createUser(employeeNumber);
		Project project = projectRepository.save(Project.builder()
			.name("Tool Approval Project " + employeeNumber)
			.createdByUser(user)
			.projectAdminUser(user)
			.build());
		ProjectMember projectMember = createProjectMember(project, user, projectRole);

		return new ProjectFixture(user, project, projectMember);
	}

	private ProjectMember createProjectMember(Project project, User user, ProjectRole projectRole) {
		return projectMemberRepository.save(ProjectMember.builder()
			.project(project)
			.user(user)
			.projectRole(projectRole)
			.canCreateTool(true)
			.canUpdateTool(true)
			.build());
	}

	private User createUser(String employeeNumber) {
		return userRepository.save(User.builder()
			.employeeNumber(employeeNumber)
			.name("Tool Approval User " + employeeNumber)
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
