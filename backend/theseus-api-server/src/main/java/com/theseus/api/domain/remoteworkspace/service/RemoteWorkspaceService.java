package com.theseus.api.domain.remoteworkspace.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.config.CoreStreamProperties;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.entity.ProjectRole;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.remoteworkspace.dto.request.RemoteWorkspaceConnectionConfigRequest;
import com.theseus.api.domain.remoteworkspace.dto.request.RemoteWorkspaceCreateRequest;
import com.theseus.api.domain.remoteworkspace.dto.request.RemoteWorkspaceUpdateRequest;
import com.theseus.api.domain.remoteworkspace.dto.response.RemoteWorkspaceConnectionConfigResponse;
import com.theseus.api.domain.remoteworkspace.dto.response.RemoteWorkspaceConnectionTestResponse;
import com.theseus.api.domain.remoteworkspace.dto.response.RemoteWorkspaceResponse;
import com.theseus.api.domain.remoteworkspace.entity.RemoteWorkspace;
import com.theseus.api.domain.remoteworkspace.entity.RemoteWorkspaceStatus;
import com.theseus.api.domain.remoteworkspace.repository.RemoteWorkspaceRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.io.IOException;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpRequest.BodyPublishers;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.List;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class RemoteWorkspaceService {

	private static final Duration CORE_CONNECTION_TEST_TIMEOUT = Duration.ofSeconds(20);
	private static final String INTERNAL_API_KEY_HEADER = "X-Internal-Api-Key";
	private static final String CONNECTION_TEST_FAILED_MESSAGE = "Remote Workspace connection test failed.";

	private final RemoteWorkspaceRepository remoteWorkspaceRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final UserRepository userRepository;
	private final CoreStreamProperties coreStreamProperties;
	private final ObjectMapper objectMapper;
	private final HttpClient httpClient = HttpClient.newBuilder()
		.connectTimeout(Duration.ofSeconds(5))
		.build();

	@Value("${internal.api-key:}")
	private String internalApiKey;

	/**
	 * 프로젝트 ADMIN 권한으로 외부 실행 대상 서버 정보를 등록합니다.
	 */
	@Transactional
	public RemoteWorkspaceResponse createRemoteWorkspace(
		AuthenticatedUser currentUser,
		Long projectId,
		RemoteWorkspaceCreateRequest request
	) {
		validateCreateRequest(request);
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);
		validateProjectAdmin(projectMember);

		RemoteWorkspace remoteWorkspace = remoteWorkspaceRepository.save(request.toEntity(project, projectMember));

		return RemoteWorkspaceResponse.createFrom(remoteWorkspace);
	}

	/**
	 * 프로젝트 멤버가 접근 가능한 RemoteWorkspace 목록을 조회합니다.
	 */
	public List<RemoteWorkspaceResponse> getRemoteWorkspaces(AuthenticatedUser currentUser, Long projectId) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		getActiveProjectMember(project, user);

		return remoteWorkspaceRepository
			.findByProjectAndStatusNotOrderByUpdatedAtDesc(project, RemoteWorkspaceStatus.DELETED)
			.stream()
			.map(RemoteWorkspaceResponse::createFrom)
			.toList();
	}

	/**
	 * 프로젝트 멤버 권한으로 단일 RemoteWorkspace 상세 정보를 조회합니다.
	 */
	public RemoteWorkspaceResponse getRemoteWorkspace(
		AuthenticatedUser currentUser,
		Long projectId,
		Long remoteWorkspaceId
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		getActiveProjectMember(project, user);
		RemoteWorkspace remoteWorkspace = getRemoteWorkspaceEntity(project, remoteWorkspaceId);

		return RemoteWorkspaceResponse.createFrom(remoteWorkspace);
	}

	/**
	 * 프로젝트 ADMIN 권한으로 RemoteWorkspace 접속 정보를 수정합니다.
	 */
	@Transactional
	public RemoteWorkspaceResponse updateRemoteWorkspace(
		AuthenticatedUser currentUser,
		Long projectId,
		Long remoteWorkspaceId,
		RemoteWorkspaceUpdateRequest request
	) {
		validateUpdateRequest(request);
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);
		validateProjectAdmin(projectMember);
		RemoteWorkspace remoteWorkspace = getRemoteWorkspaceEntity(project, remoteWorkspaceId);

		remoteWorkspace.update(
			request.getName(),
			request.getHost(),
			request.getPort(),
			request.getUsername(),
			request.getPassword(),
			request.getPrivateKeyPath(),
			request.getBasePath(),
			request.getAllowWriteExecution()
		);

		return RemoteWorkspaceResponse.createFrom(remoteWorkspace);
	}

	/**
	 * 프로젝트 ADMIN 권한으로 RemoteWorkspace를 삭제 상태로 전환합니다.
	 */
	@Transactional
	public RemoteWorkspaceResponse deleteRemoteWorkspace(
		AuthenticatedUser currentUser,
		Long projectId,
		Long remoteWorkspaceId
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);
		validateProjectAdmin(projectMember);
		RemoteWorkspace remoteWorkspace = getRemoteWorkspaceEntity(project, remoteWorkspaceId);

		remoteWorkspace.delete();

		return RemoteWorkspaceResponse.createFrom(remoteWorkspace);
	}

	/**
	 * Core Server에 Remote Workspace 연결 테스트를 요청합니다.
	 */
	public RemoteWorkspaceConnectionTestResponse testConnection(
		AuthenticatedUser currentUser,
		Long projectId,
		Long remoteWorkspaceId
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);
		validateProjectAdmin(projectMember);
		RemoteWorkspace remoteWorkspace = getRemoteWorkspaceEntity(project, remoteWorkspaceId);

		return requestCoreConnectionTest(project, remoteWorkspace);
	}

	/**
	 * Core Server가 Remote Workspace SSH 연결 직전에 사용할 내부 접속 설정을 조회합니다.
	 */
	public RemoteWorkspaceConnectionConfigResponse getConnectionConfig(RemoteWorkspaceConnectionConfigRequest request) {
		if (request == null || request.getProjectId() == null || request.getRemoteWorkspaceId() == null) {
			throw BusinessException.of(ErrorCode.REMOTE_WORKSPACE_PAYLOAD_INVALID);
		}

		Project project = getProjectEntity(request.getProjectId());
		RemoteWorkspace remoteWorkspace = getRemoteWorkspaceEntity(project, request.getRemoteWorkspaceId());
		return RemoteWorkspaceConnectionConfigResponse.createFrom(remoteWorkspace);
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

	private RemoteWorkspace getRemoteWorkspaceEntity(Project project, Long remoteWorkspaceId) {
		return remoteWorkspaceRepository
			.findByIdAndProjectAndStatusNot(remoteWorkspaceId, project, RemoteWorkspaceStatus.DELETED)
			.orElseThrow(() -> BusinessException.of(ErrorCode.REMOTE_WORKSPACE_NOT_FOUND));
	}

	private void validateProjectAdmin(ProjectMember projectMember) {
		if (!ProjectRole.ADMIN.equals(projectMember.getProjectRole())) {
			throw BusinessException.of(ErrorCode.REMOTE_WORKSPACE_ADMIN_PERMISSION_REQUIRED);
		}
	}

	private void validateCreateRequest(RemoteWorkspaceCreateRequest request) {
		if (request == null
			|| isBlank(request.getName())
			|| isBlank(request.getHost())
			|| request.getPort() == null
			|| request.getPort() < 1
			|| request.getPort() > 65535
			|| isBlank(request.getUsername())
			|| isBlank(request.getBasePath())) {
			throw BusinessException.of(ErrorCode.REMOTE_WORKSPACE_PAYLOAD_INVALID);
		}
	}

	private void validateUpdateRequest(RemoteWorkspaceUpdateRequest request) {
		if (request == null
			|| isBlankIfPresent(request.getName())
			|| isBlankIfPresent(request.getHost())
			|| isBlankIfPresent(request.getUsername())
			|| isBlankIfPresent(request.getBasePath())) {
			throw BusinessException.of(ErrorCode.REMOTE_WORKSPACE_PAYLOAD_INVALID);
		}
	}

	private boolean isBlankIfPresent(String value) {
		return value != null && value.isBlank();
	}

	private boolean isBlank(String value) {
		return value == null || value.isBlank();
	}

	private RemoteWorkspaceConnectionTestResponse requestCoreConnectionTest(
		Project project,
		RemoteWorkspace remoteWorkspace
	) {
		try {
			String requestBody = objectMapper.writeValueAsString(Map.of(
				"projectId", project.getId(),
				"remoteWorkspaceId", remoteWorkspace.getId()
			));
			HttpRequest coreRequest = HttpRequest.newBuilder(coreStreamProperties.remoteWorkspaceConnectionTestUri())
				.timeout(CORE_CONNECTION_TEST_TIMEOUT)
				.header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
				.header(HttpHeaders.ACCEPT, MediaType.APPLICATION_JSON_VALUE)
				.header(INTERNAL_API_KEY_HEADER, internalApiKey == null ? "" : internalApiKey)
				.POST(BodyPublishers.ofString(requestBody, StandardCharsets.UTF_8))
				.build();

			HttpResponse<String> response = httpClient.send(coreRequest, HttpResponse.BodyHandlers.ofString());
			if (response.statusCode() < 200 || response.statusCode() >= 300) {
				log.warn(">>>> Core Remote Workspace connection test failed. status={}", response.statusCode());
				return RemoteWorkspaceConnectionTestResponse.createFrom(
					remoteWorkspace,
					false,
					CONNECTION_TEST_FAILED_MESSAGE
				);
			}

			JsonNode result = unwrapResult(objectMapper.readTree(response.body()));
			return RemoteWorkspaceConnectionTestResponse.createFrom(
				remoteWorkspace,
				result.path("available").asBoolean(false),
				result.path("message").asText(CONNECTION_TEST_FAILED_MESSAGE)
			);
		} catch (IOException exception) {
			log.warn(">>>> Core Remote Workspace connection test request failed.", exception);
			return RemoteWorkspaceConnectionTestResponse.createFrom(
				remoteWorkspace,
				false,
				CONNECTION_TEST_FAILED_MESSAGE
			);
		} catch (InterruptedException exception) {
			Thread.currentThread().interrupt();
			log.warn(">>>> Core Remote Workspace connection test was interrupted.", exception);
			return RemoteWorkspaceConnectionTestResponse.createFrom(
				remoteWorkspace,
				false,
				CONNECTION_TEST_FAILED_MESSAGE
			);
		}
	}

	private JsonNode unwrapResult(JsonNode responseBody) {
		if (responseBody.has("isSuccess") && responseBody.has("result")) {
			return responseBody.path("result");
		}
		return responseBody;
	}
}
