package com.theseus.api.domain.project.service;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.project.dto.request.InternalProjectPermissionRequest;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.entity.UserStatus;
import com.theseus.api.domain.user.repository.UserRepository;
import java.util.LinkedHashMap;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class InternalProjectPermissionService {

	private static final int BLOCKED_PERMISSION_LEVEL = 999;

	private static final Map<String, Integer> DEFAULT_TOOL_PERMISSIONS = Map.ofEntries(
		Map.entry("bash", 3),
		Map.entry("read_file", 1),
		Map.entry("write_file", 2),
		Map.entry("edit_file", 2),
		Map.entry("glob", 1),
		Map.entry("grep", 1),
		Map.entry("web_search", 1),
		Map.entry("web_fetch", 1),
		Map.entry("dummy_echo", 1),
		Map.entry("system_reboot", 5)
	);

	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final UserRepository userRepository;

	public Map<String, Integer> getToolPermissions(InternalProjectPermissionRequest request) {
		ProjectMember projectMember = getActiveProjectMember(request.getProjectId(), request.getUserId());

		if (!Boolean.TRUE.equals(projectMember.getCanUseTool())) {
			throw BusinessException.of(ErrorCode.TOOL_USE_PERMISSION_REQUIRED);
		}

		Map<String, Integer> permissions = new LinkedHashMap<>(DEFAULT_TOOL_PERMISSIONS);
		permissions.put(
			"create_tool",
			Boolean.TRUE.equals(projectMember.getCanCreateTool()) ? 2 : BLOCKED_PERMISSION_LEVEL
		);

		return permissions;
	}

	private ProjectMember getActiveProjectMember(Long projectId, Long userId) {
		Project project = projectRepository.findById(projectId)
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_NOT_FOUND));
		User user = userRepository.findById(userId)
			.orElseThrow(() -> BusinessException.of(ErrorCode.USER_NOT_FOUND));

		if (!UserStatus.ACTIVE.equals(user.getStatus())) {
			throw BusinessException.of(ErrorCode.PROJECT_MEMBER_ACTIVE_USER_REQUIRED);
		}

		ProjectMember projectMember = projectMemberRepository.findByProjectAndUser(project, user)
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_MEMBER_PERMISSION_REQUIRED));

		if (!ProjectMemberStatus.IN_PROGRESS.equals(projectMember.getStatus())) {
			throw BusinessException.of(ErrorCode.ACTIVE_PROJECT_MEMBER_REQUIRED);
		}

		return projectMember;
	}
}
