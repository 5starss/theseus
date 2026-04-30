package com.theseus.api.domain.tool.service;

import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.tool.dto.response.ToolDetailResponse;
import com.theseus.api.domain.tool.dto.response.ToolSummaryResponse;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolStatus;
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
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
public class ToolService {

	private static final String ACCESSIBLE_SCOPE = "accessible";

	private final ToolRepository toolRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final UserRepository userRepository;

	public Page<ToolSummaryResponse> getTools(
		AuthenticatedUser currentUser,
		Long projectId,
		String scope,
		ToolStatus status,
		int page,
		int size
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);

		validateAccessibleScope(scope);
		validateApprovedStatus(status);
		validateToolUsePermission(projectMember);

		Pageable pageable = createPageable(page, size);
		return toolRepository.findAccessibleByProjectAndStatus(
				project,
				ToolStatus.APPROVED,
				projectMember.getAccessLevel(),
				pageable
			)
			.map(ToolSummaryResponse::createFrom);
	}

	public ToolDetailResponse getTool(
		AuthenticatedUser currentUser,
		Long projectId,
		Long toolId
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);
		validateToolUsePermission(projectMember);

		Tool tool = getToolEntity(project, toolId);
		validateApprovedStatus(tool.getStatus());
		validateAccessibleTool(projectMember, tool);

		return ToolDetailResponse.createFrom(tool);
	}

	private User getCurrentUserEntity(AuthenticatedUser currentUser) {
		if (currentUser == null) {
			throw new ResponseStatusException(HttpStatus.UNAUTHORIZED, "인증 정보가 없습니다.");
		}

		return userRepository.findById(currentUser.userId())
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "사용자를 찾을 수 없습니다."));
	}

	private Project getProjectEntity(Long projectId) {
		return projectRepository.findById(projectId)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "프로젝트를 찾을 수 없습니다."));
	}

	private ProjectMember getActiveProjectMember(Project project, User user) {
		ProjectMember projectMember = projectMemberRepository.findByProjectAndUser(project, user)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.FORBIDDEN, "프로젝트 멤버 권한이 필요합니다."));

		if (!ProjectMemberStatus.IN_PROGRESS.equals(projectMember.getStatus())) {
			throw new ResponseStatusException(HttpStatus.FORBIDDEN, "진행 중인 프로젝트 멤버만 접근할 수 있습니다.");
		}

		return projectMember;
	}

	private Tool getToolEntity(Project project, Long toolId) {
		return toolRepository.findByIdAndProjectAndStatusNot(toolId, project, ToolStatus.DELETED)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Tool을 찾을 수 없습니다."));
	}

	private void validateAccessibleScope(String scope) {
		if (!ACCESSIBLE_SCOPE.equals(scope)) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "지원하지 않는 Tool 조회 범위입니다.");
		}
	}

	private void validateApprovedStatus(ToolStatus status) {
		if (!ToolStatus.APPROVED.equals(status)) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "승인된 Tool만 조회할 수 있습니다.");
		}
	}

	private void validateToolUsePermission(ProjectMember projectMember) {
		if (!Boolean.TRUE.equals(projectMember.getCanUseTool())) {
			throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Tool 사용 권한이 필요합니다.");
		}
	}

	private void validateAccessibleTool(ProjectMember projectMember, Tool tool) {
		if (!tool.isAccessibleWithAccessLevel(projectMember.getAccessLevel())) {
			throw new ResponseStatusException(HttpStatus.FORBIDDEN, "Tool 접근 레벨이 부족합니다.");
		}
	}

	private Pageable createPageable(int page, int size) {
		return PageRequest.of(Math.max(page, 0), Math.max(size, 1));
	}
}
