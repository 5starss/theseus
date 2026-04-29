package com.theseus.api.domain.tool.service;

import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.tool.dto.response.ToolApprovalResponse;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolApproval;
import com.theseus.api.domain.tool.repository.ToolApprovalRepository;
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.util.List;
import java.util.Objects;
import lombok.RequiredArgsConstructor;
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
}
