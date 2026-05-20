package com.theseus.api.domain.tool.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
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
import com.theseus.api.domain.chat.config.CoreStreamProperties;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ToolService {

	private static final String ACCESSIBLE_SCOPE = "accessible";

	private final ToolRepository toolRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final UserRepository userRepository;
	private final CoreStreamProperties coreStreamProperties;
	private final ObjectMapper objectMapper;

	private final java.net.http.HttpClient httpClient = java.net.http.HttpClient.newBuilder()
		.connectTimeout(java.time.Duration.ofSeconds(5))
		.build();

	@Value("${internal.api-key:}")
	private String internalApiKey;

	/**
	 * 프로젝트 멤버가 사용할 수 있는 승인 완료 Tool 목록을 조회합니다.
	 */
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

	/**
	 * 접근 권한과 등급 조건을 검증하고 Tool 상세 정보를 조회합니다.
	 */
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

	@Transactional
	public ToolSummaryResponse updateToolAccessLevel(
		AuthenticatedUser currentUser,
		Long projectId,
		Long toolId,
		Integer accessLevel
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);
		validateProjectAdmin(projectMember);
		validateToolAccessLevel(accessLevel);

		Tool tool = toolRepository.findByIdAndProjectForUpdate(toolId, project)
			.orElseThrow(() -> BusinessException.of(ErrorCode.TOOL_NOT_FOUND));
		if (tool.isDeleted()) {
			throw BusinessException.of(ErrorCode.TOOL_NOT_FOUND);
		}

		requestCoreToolPermissionLevelUpdate(project.getId(), tool.getFileName(), accessLevel);
		tool.updateAccessLevel(accessLevel, updatePermissionLevelMetadata(tool.getMetadataJson(), accessLevel));
		return ToolSummaryResponse.createFrom(tool);
	}

	/**
	 * Tool을 논리 삭제 처리하고 코어서버의 실제 도구 파일을 휴지통으로 이동시킵니다.
	 */
	@Transactional
	public void deleteTool(AuthenticatedUser currentUser, Long projectId, Long toolId) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);
		validateToolUsePermission(projectMember);

		Tool tool = getToolEntity(project, toolId);

		// 코어서버의 실제 도구 파일(.py, .meta.json) 휴지통 이동 API 호출
		requestCoreToolDeletion(project.getId(), tool.getFileName());

		tool.delete();
	}

	private void requestCoreToolDeletion(Long projectId, String fileName) {
		try {
			java.net.URI deleteUri = coreStreamProperties.deleteToolUri(projectId, fileName);
			java.net.http.HttpRequest coreRequest = java.net.http.HttpRequest.newBuilder(deleteUri)
				.timeout(java.time.Duration.ofSeconds(10))
				.header("Accept", "application/json")
				.header("X-Internal-Api-Key", internalApiKey == null ? "" : internalApiKey)
				.DELETE()
				.build();

			java.net.http.HttpResponse<String> response = httpClient.send(coreRequest, java.net.http.HttpResponse.BodyHandlers.ofString());
			if (response.statusCode() < 200 || response.statusCode() >= 300) {
				log.warn(">>>> Core Tool deletion failed. status={}, body={}", response.statusCode(), response.body());
			} else {
				log.info(">>>> Successfully requested Core Tool deletion to trash. status={}", response.statusCode());
			}
		} catch (Exception exception) {
			log.warn(">>>> Failed to send Tool deletion request to Core server. project={}, file={}", projectId, fileName, exception);
		}
	}

	private void requestCoreToolPermissionLevelUpdate(Long projectId, String fileName, Integer accessLevel) {
		try {
			java.net.URI updateUri = coreStreamProperties.updateToolPermissionLevelUri(projectId, fileName);
			String requestBody = "{\"permissionLevel\":%d}".formatted(accessLevel);
			java.net.http.HttpRequest coreRequest = java.net.http.HttpRequest.newBuilder(updateUri)
				.timeout(java.time.Duration.ofSeconds(10))
				.header("Accept", "application/json")
				.header("Content-Type", "application/json")
				.header("X-Internal-Api-Key", internalApiKey == null ? "" : internalApiKey)
				.method("PATCH", java.net.http.HttpRequest.BodyPublishers.ofString(requestBody))
				.build();

			java.net.http.HttpResponse<String> response = httpClient.send(coreRequest, java.net.http.HttpResponse.BodyHandlers.ofString());
			if (response.statusCode() < 200 || response.statusCode() >= 300) {
				log.warn(">>>> Core Tool permissionLevel update failed. status={}, body={}", response.statusCode(), response.body());
			}
		} catch (Exception exception) {
			log.warn(">>>> Failed to send Tool permissionLevel update request to Core server. project={}, file={}", projectId, fileName, exception);
		}
	}

	private User getCurrentUserEntity(AuthenticatedUser currentUser) {
		if (currentUser == null) {
			throw BusinessException.of(ErrorCode.UNAUTHORIZED);
		}

		return userRepository.findById(currentUser.userId())
			.orElseThrow(() -> BusinessException.of(ErrorCode.USER_NOT_FOUND));
	}

	private Project getProjectEntity(Long projectId) {
		return projectRepository.findById(projectId)
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_NOT_FOUND));
	}

	private ProjectMember getActiveProjectMember(Project project, User user) {
		ProjectMember projectMember = projectMemberRepository.findByProjectAndUser(project, user)
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_MEMBER_PERMISSION_REQUIRED));

		if (!ProjectMemberStatus.IN_PROGRESS.equals(projectMember.getStatus())) {
			throw BusinessException.of(ErrorCode.ACTIVE_PROJECT_MEMBER_REQUIRED);
		}

		return projectMember;
	}

	private Tool getToolEntity(Project project, Long toolId) {
		return toolRepository.findByIdAndProjectAndStatusNot(toolId, project, ToolStatus.DELETED)
			.orElseThrow(() -> BusinessException.of(ErrorCode.TOOL_NOT_FOUND));
	}

	private void validateAccessibleScope(String scope) {
		if (!ACCESSIBLE_SCOPE.equals(scope)) {
			throw BusinessException.of(ErrorCode.UNSUPPORTED_TOOL_SCOPE);
		}
	}

	private void validateApprovedStatus(ToolStatus status) {
		if (!ToolStatus.APPROVED.equals(status)) {
			throw BusinessException.of(ErrorCode.APPROVED_TOOL_ONLY);
		}
	}

	private void validateToolUsePermission(ProjectMember projectMember) {
		if (!Boolean.TRUE.equals(projectMember.getCanUseTool())) {
			throw BusinessException.of(ErrorCode.TOOL_USE_PERMISSION_REQUIRED);
		}
	}

	private void validateAccessibleTool(ProjectMember projectMember, Tool tool) {
		if (!tool.isAccessibleWithAccessLevel(projectMember.getAccessLevel())) {
			throw BusinessException.of(ErrorCode.TOOL_ACCESS_LEVEL_REQUIRED);
		}
	}

	private void validateProjectAdmin(ProjectMember projectMember) {
		if (!ProjectRole.ADMIN.equals(projectMember.getProjectRole())) {
			throw BusinessException.of(ErrorCode.PROJECT_ADMIN_PERMISSION_REQUIRED);
		}
	}

	private void validateToolAccessLevel(Integer accessLevel) {
		if (accessLevel == null || accessLevel < 1 || accessLevel > 5) {
			throw BusinessException.of(ErrorCode.TOOL_ACCESS_LEVEL_INVALID);
		}
	}

	private String updatePermissionLevelMetadata(String metadataJson, Integer accessLevel) {
		ObjectNode metadata = objectMapper.createObjectNode();
		if (metadataJson != null && !metadataJson.isBlank()) {
			try {
				var parsed = objectMapper.readTree(metadataJson);
				if (parsed != null && parsed.isObject()) {
					metadata = (ObjectNode) parsed;
				}
			} catch (JsonProcessingException exception) {
				log.warn(">>>> Tool metadataJson parse failed while updating access level.", exception);
			}
		}
		metadata.put("permissionLevel", accessLevel);
		try {
			return objectMapper.writeValueAsString(metadata);
		} catch (JsonProcessingException exception) {
			throw BusinessException.of(ErrorCode.TOOL_ACCESS_LEVEL_INVALID, exception);
		}
	}

	private Pageable createPageable(int page, int size) {
		return PageRequest.of(Math.max(page, 0), Math.max(size, 1));
	}
}
