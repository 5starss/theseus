package com.theseus.api.domain.tool.service;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.entity.ChatMessage;
import com.theseus.api.domain.chat.entity.ChatMessageContentType;
import com.theseus.api.domain.chat.entity.ChatMessageSenderType;
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
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolApproval;
import com.theseus.api.domain.tool.entity.ToolApprovalStatus;
import com.theseus.api.domain.tool.entity.ToolDraftPhase;
import com.theseus.api.domain.tool.entity.ToolPlan;
import com.theseus.api.domain.tool.entity.ToolPlanGroup;
import com.theseus.api.domain.tool.entity.ToolPlanGroupStatus;
import com.theseus.api.domain.tool.entity.ToolPlanRun;
import com.theseus.api.domain.tool.entity.ToolPlanRunRequestType;
import com.theseus.api.domain.tool.entity.ToolPlanRunStatus;
import com.theseus.api.domain.tool.entity.ToolPlanStatus;
import com.theseus.api.domain.tool.entity.ToolStatus;
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
import org.springframework.data.domain.Page;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.annotation.Transactional;

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
	@DisplayName("Project ADMIN can get ToolApproval list filtered by approval status")
	void getToolApprovals() {
		// Given
		ProjectFixture fixture = createProjectFixture("A142001");
		ToolApproval firstPendingApproval = createPendingToolApproval(fixture);
		User secondCreatorUser = createUser("A142002");
		ProjectMember secondCreator = createProjectMember(fixture.project(), secondCreatorUser, ProjectRole.MEMBER);
		ToolApproval secondPendingApproval = createPendingToolApproval(
			fixture.project(),
			secondCreatorUser,
			secondCreator
		);
		User reviewedCreatorUser = createUser("A142003");
		ProjectMember reviewedCreator = createProjectMember(fixture.project(), reviewedCreatorUser, ProjectRole.MEMBER);
		ToolApproval reviewedApproval = createPendingToolApproval(
			fixture.project(),
			reviewedCreatorUser,
			reviewedCreator
		);
		toolApprovalService.approveToolApproval(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			reviewedApproval.getId(),
			createApproveRequest(3, "approved")
		);

		// When
		Page<ToolApprovalResponse> response = toolApprovalService.getToolApprovals(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			ToolApprovalStatus.PENDING,
			0,
			20
		);

		// Then
		assertThat(response.getTotalElements()).isEqualTo(2);
		assertThat(response.getContent())
			.extracting(ToolApprovalResponse::getToolApprovalId)
			.containsExactlyInAnyOrder(firstPendingApproval.getId(), secondPendingApproval.getId())
			.doesNotContain(reviewedApproval.getId());
		assertThat(response.getContent())
			.extracting(ToolApprovalResponse::getApprovalStatus)
			.containsOnly(ToolApprovalStatus.PENDING);
	}

	@Test
	@DisplayName("Project MANAGER can get ToolApproval detail")
	void getToolApproval() {
		// Given
		ProjectFixture fixture = createProjectFixture("A142011");
		User managerUser = createUser("A142012");
		createProjectMember(fixture.project(), managerUser, ProjectRole.MANAGER);
		ToolApproval toolApproval = createPendingToolApproval(fixture);

		// When
		ToolApprovalResponse response = toolApprovalService.getToolApproval(
			createAuthenticatedUser(managerUser),
			fixture.project().getId(),
			toolApproval.getId()
		);

		// Then
		assertThat(response.getToolApprovalId()).isEqualTo(toolApproval.getId());
		assertThat(response.getProjectId()).isEqualTo(fixture.project().getId());
		assertThat(response.getToolId()).isEqualTo(toolApproval.getTool().getId());
		assertThat(response.getFileName()).isEqualTo(toolApproval.getTool().getFileName());
		assertThat(response.getRequestedByProjectMemberId()).isEqualTo(fixture.projectMember().getId());
		assertThat(response.getRequestedByUserId()).isEqualTo(fixture.user().getId());
		assertThat(response.getRequestedByUserName()).isEqualTo(fixture.user().getName());
	}

	@Test
	@DisplayName("Project MEMBER cannot get ToolApproval list")
	void getToolApprovalsFailsWhenReviewerIsMember() {
		// Given
		ProjectFixture fixture = createProjectFixture("A142021");
		User memberUser = createUser("A142022");
		createProjectMember(fixture.project(), memberUser, ProjectRole.MEMBER);
		createPendingToolApproval(fixture);

		// When & Then
		assertThatThrownBy(() -> toolApprovalService.getToolApprovals(
			createAuthenticatedUser(memberUser),
			fixture.project().getId(),
			ToolApprovalStatus.PENDING,
			0,
			20
		))
			.isInstanceOf(BusinessException.class)
			.extracting(exception -> ((BusinessException) exception).getErrorCode())
			.isEqualTo(ErrorCode.TOOL_APPROVAL_REVIEWER_REQUIRED);
	}

	@Test
	@DisplayName("Non-project member cannot get ToolApproval detail")
	void getToolApprovalFailsWhenCurrentUserIsNotProjectMember() {
		// Given
		ProjectFixture fixture = createProjectFixture("A142031");
		ToolApproval toolApproval = createPendingToolApproval(fixture);
		User outsider = createUser("A142032");

		// When & Then
		assertThatThrownBy(() -> toolApprovalService.getToolApproval(
			createAuthenticatedUser(outsider),
			fixture.project().getId(),
			toolApproval.getId()
		))
			.isInstanceOf(BusinessException.class)
			.extracting(exception -> ((BusinessException) exception).getErrorCode())
			.isEqualTo(ErrorCode.PROJECT_MEMBER_PERMISSION_REQUIRED);
	}

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
		ChatMessage savedMessage = chatMessageRepository.findByChatSessionAndToolOrderByMessageOrderAsc(
			tool.getChatSession(),
			tool
		).getFirst();
		assertThat(response.getRequestNumber()).isEqualTo(1);
		assertThat(response.getApprovalStatus()).isEqualTo(ToolApprovalStatus.PENDING);
		assertThat(response.getToolStatus()).isEqualTo(ToolStatus.PENDING);
		assertThat(response.getDraftPhase()).isEqualTo(ToolDraftPhase.REVIEW);
		assertThat(response.getRequestedAt()).isNotNull();
		assertThat(savedTool.getStatus()).isEqualTo(ToolStatus.PENDING);
		assertThat(savedToolApproval.getRequestedByProjectMember().getId()).isEqualTo(fixture.projectMember().getId());
		assertThat(savedMessage.getSenderType()).isEqualTo(ChatMessageSenderType.USER);
		assertThat(savedMessage.getMessageType()).isEqualTo(ChatMessageType.TOOL_APPROVAL_REQUEST);
		assertThat(savedMessage.getContentType()).isEqualTo(ChatMessageContentType.JSON);
		assertThat(savedMessage.getContent()).contains(
			"\"toolApprovalId\":" + response.getToolApprovalId(),
			"\"toolId\":" + tool.getId(),
			"\"requestNumber\":1",
			"\"approvalStatus\":\"PENDING\""
		);
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
			.isInstanceOf(BusinessException.class)
			.extracting(exception -> ((BusinessException) exception).getErrorCode())
			.isEqualTo(ErrorCode.TOOL_APPROVAL_CREATOR_REQUIRED);
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
			.isInstanceOf(BusinessException.class)
			.extracting(exception -> ((BusinessException) exception).getErrorCode())
			.isEqualTo(ErrorCode.TOOL_APPROVAL_REVIEW_PHASE_REQUIRED);
	}

	@Test
	@DisplayName("REVIEW 상태의 ToolPlan은 생성자가 승인 요청할 수 있다")
	void requestToolPlanApproval() {
		// Given
		ProjectFixture fixture = createProjectFixture("A252001");
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
		assertThat(response.getToolId()).isNull();
		assertThat(response.getToolPlanId()).isEqualTo(toolPlan.getId());
		assertThat(response.getPlanGroupId()).isEqualTo(toolPlan.getPlanGroup().getId());
		assertThat(response.getPlanVersion()).isEqualTo(1L);
		assertThat(response.getApprovalStatus()).isEqualTo(ToolApprovalStatus.PENDING);
		assertThat(response.getToolPlanStatus()).isEqualTo(ToolPlanStatus.PENDING);
		assertThat(savedToolApproval.getTool()).isNull();
		assertThat(savedToolApproval.getToolPlan().getId()).isEqualTo(toolPlan.getId());
		assertThat(savedToolPlan.getStatus()).isEqualTo(ToolPlanStatus.PENDING);
		assertThat(savedToolPlan.getPlanGroup().getStatus()).isEqualTo(ToolPlanGroupStatus.PENDING);
		assertThat(savedMessage.getSenderType()).isEqualTo(ChatMessageSenderType.USER);
		assertThat(savedMessage.getMessageType()).isEqualTo(ChatMessageType.TOOL_APPROVAL_REQUEST);
		assertThat(savedMessage.getContent()).contains(
			"\"toolApprovalId\":" + response.getToolApprovalId(),
			"\"toolPlanId\":" + toolPlan.getId(),
			"\"requestNumber\":1"
		);
	}

	@Test
	@DisplayName("REVIEW 상태가 아닌 ToolPlan은 승인 요청할 수 없다")
	void requestToolPlanApprovalFailsWhenPlanIsNotReview() {
		// Given
		ProjectFixture fixture = createProjectFixture("A252011");
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
	@DisplayName("ToolPlan 승인 시 build 요청 Run을 만들고 Tool은 생성하지 않는다")
	void approveToolPlanApprovalCreatesBuildRunWithoutTool() {
		// Given
		ProjectFixture fixture = createProjectFixture("A252021");
		ToolApproval toolApproval = createPendingToolPlanApproval(fixture);
		ToolPlan toolPlan = toolApproval.getToolPlan();

		// When
		ToolApprovalResponse response = toolApprovalService.approveToolApproval(
			createAuthenticatedUser(fixture.user()),
			fixture.project().getId(),
			toolApproval.getId(),
			createApproveRequest(null, "approved")
		);

		// Then
		ToolApproval savedToolApproval = toolApprovalRepository.findById(toolApproval.getId()).orElseThrow();
		ToolPlan savedToolPlan = toolPlanRepository.findById(toolPlan.getId()).orElseThrow();
		ToolPlanGroup savedPlanGroup = toolPlanGroupRepository.findById(savedToolPlan.getPlanGroup().getId())
			.orElseThrow();
		ToolPlanRun savedBuildRun = toolPlanRunRepository.findByProjectAndChatSessionAndStatusOrderByRequestedAtDesc(
			fixture.project(),
			savedToolPlan.getChatSession(),
			ToolPlanRunStatus.REQUESTED
		).getFirst();
		assertThat(response.getToolId()).isNull();
		assertThat(response.getToolPlanId()).isEqualTo(toolPlan.getId());
		assertThat(response.getApprovalStatus()).isEqualTo(ToolApprovalStatus.APPROVED);
		assertThat(response.getToolPlanStatus()).isEqualTo(ToolPlanStatus.APPROVED);
		assertThat(response.getReviewedByProjectMemberId()).isEqualTo(fixture.projectMember().getId());
		assertThat(savedToolApproval.getTool()).isNull();
		assertThat(savedToolApproval.getToolPlan().getId()).isEqualTo(toolPlan.getId());
		assertThat(savedToolPlan.getStatus()).isEqualTo(ToolPlanStatus.APPROVED);
		assertThat(savedPlanGroup.getStatus()).isEqualTo(ToolPlanGroupStatus.APPROVED);
		assertThat(savedPlanGroup.getApprovedToolPlan().getId()).isEqualTo(toolPlan.getId());
		assertThat(savedBuildRun.getRequestType()).isEqualTo(ToolPlanRunRequestType.BUILD_TOOL);
		assertThat(savedBuildRun.getBaseToolPlan().getId()).isEqualTo(toolPlan.getId());
		assertThat(savedBuildRun.getPlanGroup().getId()).isEqualTo(savedPlanGroup.getId());
		assertThat(savedBuildRun.getRequestPayloadJson()).contains(
			"\"eventType\":\"TOOL_BUILD_REQUESTED\"",
			"\"toolPlanId\":" + toolPlan.getId(),
			"\"planGroupId\":" + savedPlanGroup.getId(),
			"\"approvedByProjectMemberId\":" + fixture.projectMember().getId()
		);
		assertThat(toolRepository.findByProjectAndStatusNotOrderByUpdatedAtDesc(
			fixture.project(),
			ToolStatus.DELETED
		)).isEmpty();
	}

	@Test
	@DisplayName("ToolPlan 반려 시 ToolPlan과 그룹을 REJECTED로 변경하고 Tool은 생성하지 않는다")
	void rejectToolPlanApproval() {
		// Given
		ProjectFixture creatorFixture = createProjectFixture("A252031");
		User managerUser = createUser("A252032");
		ProjectMember manager = createProjectMember(creatorFixture.project(), managerUser, ProjectRole.MANAGER);
		ToolApproval toolApproval = createPendingToolPlanApproval(creatorFixture);
		ToolPlan toolPlan = toolApproval.getToolPlan();

		// When
		ToolApprovalResponse response = toolApprovalService.rejectToolApproval(
			createAuthenticatedUser(managerUser),
			creatorFixture.project().getId(),
			toolApproval.getId(),
			createRejectRequest("needs revision")
		);

		// Then
		ToolPlan savedToolPlan = toolPlanRepository.findById(toolPlan.getId()).orElseThrow();
		ToolPlanGroup savedPlanGroup = toolPlanGroupRepository.findById(savedToolPlan.getPlanGroup().getId())
			.orElseThrow();
		ChatMessage savedNotice = chatMessageRepository.findByToolPlanOrderByMessageOrderAsc(savedToolPlan)
			.stream()
			.filter(chatMessage -> ChatMessageType.SYSTEM_NOTICE.equals(chatMessage.getMessageType()))
			.findFirst()
			.orElseThrow();
		assertThat(response.getToolId()).isNull();
		assertThat(response.getToolPlanId()).isEqualTo(toolPlan.getId());
		assertThat(response.getApprovalStatus()).isEqualTo(ToolApprovalStatus.REJECTED);
		assertThat(response.getToolPlanStatus()).isEqualTo(ToolPlanStatus.REJECTED);
		assertThat(response.getReviewedByProjectMemberId()).isEqualTo(manager.getId());
		assertThat(response.getReviewFeedback()).isEqualTo("needs revision");
		assertThat(savedToolPlan.getStatus()).isEqualTo(ToolPlanStatus.REJECTED);
		assertThat(savedPlanGroup.getStatus()).isEqualTo(ToolPlanGroupStatus.REJECTED);
		assertThat(savedNotice.getSenderType()).isEqualTo(ChatMessageSenderType.SYSTEM);
		assertThat(savedNotice.getMessageType()).isEqualTo(ChatMessageType.SYSTEM_NOTICE);
		assertThat(savedNotice.getContent()).contains(
			"toolApprovalId=" + toolApproval.getId(),
			"toolPlanId=" + toolPlan.getId()
		);
		assertThat(toolRepository.findByProjectAndStatusNotOrderByUpdatedAtDesc(
			creatorFixture.project(),
			ToolStatus.DELETED
		)).isEmpty();
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
			.isInstanceOf(BusinessException.class)
			.extracting(exception -> ((BusinessException) exception).getErrorCode())
			.isEqualTo(ErrorCode.TOOL_APPROVAL_REVIEWER_REQUIRED);
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
			.isInstanceOf(BusinessException.class)
			.extracting(exception -> ((BusinessException) exception).getErrorCode())
			.isEqualTo(ErrorCode.TOOL_APPROVAL_ALREADY_REVIEWED);
	}

	private ToolApproval createPendingToolApproval(ProjectFixture fixture) {
		return createPendingToolApproval(fixture.project(), fixture.user(), fixture.projectMember());
	}

	private ToolApproval createPendingToolApproval(Project project, User creatorUser, ProjectMember creator) {
		Tool tool = createReviewPhaseDraftTool(project, creator);
		ToolApprovalResponse response = toolApprovalService.requestToolApproval(
			createAuthenticatedUser(creatorUser),
			project.getId(),
			tool.getId()
		);

		return toolApprovalRepository.findById(response.getToolApprovalId()).orElseThrow();
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
			.rawMarkdown("## PLAN")
			.structuredPlanJson("{\"blocks\":[{\"blockId\":\"summary\",\"title\":\"요약\",\"content\":\"내용\"}]}")
			.planSnapshot("{\"schemaVersion\":\"1.0\",\"planVersion\":1}")
			.build());
		planGroup.markReview(toolPlan);

		return toolPlan;
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
