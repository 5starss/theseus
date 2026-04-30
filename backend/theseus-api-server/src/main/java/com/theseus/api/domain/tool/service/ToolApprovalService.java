package com.theseus.api.domain.tool.service;

import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.tool.dto.request.ToolApprovalApproveRequest;
import com.theseus.api.domain.tool.dto.request.ToolApprovalRejectRequest;
import com.theseus.api.domain.tool.dto.response.ToolApprovalResponse;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolApproval;
import com.theseus.api.domain.tool.entity.ToolApprovalStatus;
import com.theseus.api.domain.tool.repository.ToolApprovalRepository;
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.util.List;
import java.util.Objects;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ToolApprovalService {

	private final ToolApprovalRepository toolApprovalRepository;
	private final ToolRepository toolRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final UserRepository userRepository;

	public Page<ToolApprovalResponse> getToolApprovals(
		AuthenticatedUser currentUser,
		Long projectId,
		ToolApprovalStatus approvalStatus,
		int page,
		int size
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember reviewer = getActiveProjectMember(project, user);
		validateToolReviewer(reviewer);

		Pageable pageable = createPageable(page, size);
		Page<ToolApproval> toolApprovals = approvalStatus == null
			? toolApprovalRepository.findByProject(project, pageable)
			: toolApprovalRepository.findByProjectAndApprovalStatus(project, approvalStatus, pageable);

		return toolApprovals
			.map(ToolApprovalResponse::createFrom);
	}

	public ToolApprovalResponse getToolApproval(
		AuthenticatedUser currentUser,
		Long projectId,
		Long toolApprovalId
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember reviewer = getActiveProjectMember(project, user);
		validateToolReviewer(reviewer);

		ToolApproval toolApproval = toolApprovalRepository.findByIdAndToolProject(toolApprovalId, project)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Tool approval was not found."));

		return ToolApprovalResponse.createFrom(toolApproval);
	}

	@Transactional
	public ToolApprovalResponse requestToolApproval(
		AuthenticatedUser currentUser,
		Long projectId,
		Long toolId
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);
		Tool tool = getToolForUpdate(project, toolId);

		validateToolCreator(tool, projectMember);
		validateRequestableTool(tool);

		ToolApproval toolApproval = toolApprovalRepository.save(ToolApproval.builder()
			.tool(tool)
			.requestNumber(getNextRequestNumber(tool))
			.requestedByProjectMember(projectMember)
			.build());
		tool.requestApproval();

		return ToolApprovalResponse.createFrom(toolApproval);
	}

	@Transactional
	public ToolApprovalResponse approveToolApproval(
		AuthenticatedUser currentUser,
		Long projectId,
		Long toolApprovalId,
		ToolApprovalApproveRequest request
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember reviewer = getActiveProjectMember(project, user);
		validateToolReviewer(reviewer);
		ToolApproval toolApproval = getToolApprovalForUpdate(project, toolApprovalId);
		Tool tool = toolApproval.getTool();

		validateReviewableToolApproval(toolApproval);
		validatePendingTool(tool);

		toolApproval.approve(reviewer, request.getReviewFeedback());
		tool.approve(request.getToolGrade());

		return ToolApprovalResponse.createFrom(toolApproval);
	}

	@Transactional
	public ToolApprovalResponse rejectToolApproval(
		AuthenticatedUser currentUser,
		Long projectId,
		Long toolApprovalId,
		ToolApprovalRejectRequest request
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember reviewer = getActiveProjectMember(project, user);
		validateToolReviewer(reviewer);
		ToolApproval toolApproval = getToolApprovalForUpdate(project, toolApprovalId);
		Tool tool = toolApproval.getTool();

		validateReviewableToolApproval(toolApproval);
		validatePendingTool(tool);

		toolApproval.reject(reviewer, request.getReviewFeedback());
		tool.reject();

		return ToolApprovalResponse.createFrom(toolApproval);
	}

	private Integer getNextRequestNumber(Tool tool) {
		List<ToolApproval> toolApprovals = toolApprovalRepository.findByToolOrderByRequestNumberDescForUpdate(tool);

		return toolApprovals.stream()
			.findFirst()
			.map(toolApproval -> toolApproval.getRequestNumber() + 1)
			.orElse(1);
	}

	private User getCurrentUserEntity(AuthenticatedUser currentUser) {
		if (currentUser == null) {
			throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "Authentication is required.");
		}

		return userRepository.findById(currentUser.userId())
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "User was not found."));
	}

	private Project getProjectEntity(Long projectId) {
		return projectRepository.findById(projectId)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Project was not found."));
	}

	private ProjectMember getActiveProjectMember(Project project, User user) {
		ProjectMember projectMember = projectMemberRepository.findByProjectAndUser(project, user)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.FORBIDDEN, "Project member permission is required."));

		if (!ProjectMemberStatus.IN_PROGRESS.equals(projectMember.getStatus())) {
			throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Active project member permission is required.");
		}

		return projectMember;
	}

	private Tool getToolForUpdate(Project project, Long toolId) {
		return toolRepository.findByIdAndProjectForUpdate(toolId, project)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Tool was not found."));
	}

	private ToolApproval getToolApprovalForUpdate(Project project, Long toolApprovalId) {
		return toolApprovalRepository.findByIdAndToolProjectForUpdate(toolApprovalId, project)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Tool approval was not found."));
	}

	private void validateToolCreator(Tool tool, ProjectMember projectMember) {
		if (!Objects.equals(tool.getCreatedByProjectMember().getId(), projectMember.getId())) {
			throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Only the Tool creator can request approval.");
		}
	}

	private void validateRequestableTool(Tool tool) {
		if (!tool.canRequestApproval()) {
			throw new ResponseStatusException(HttpStatus.CONFLICT, "Only REVIEW phase Draft Tool can request approval.");
		}
	}

	private void validateToolReviewer(ProjectMember projectMember) {
		if (!ProjectRole.ADMIN.equals(projectMember.getProjectRole())
			&& !ProjectRole.MANAGER.equals(projectMember.getProjectRole())) {
			throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Project ADMIN or MANAGER permission is required.");
		}
	}

	private void validateReviewableToolApproval(ToolApproval toolApproval) {
		if (!toolApproval.isPending()) {
			throw new ResponseStatusException(HttpStatus.CONFLICT, "Tool approval request is already reviewed.");
		}
	}

	private void validatePendingTool(Tool tool) {
		if (!tool.isPending()) {
			throw new ResponseStatusException(HttpStatus.CONFLICT, "Only pending Tool can be reviewed.");
		}
	}

	private Pageable createPageable(int page, int size) {
		return PageRequest.of(Math.max(page, 0), Math.max(size, 1));
	}
}
