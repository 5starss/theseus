package com.theseus.api.domain.remoteworkspace.service;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;
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
import com.theseus.api.domain.remoteworkspace.dto.request.RemoteWorkspaceCreateRequest;
import com.theseus.api.domain.remoteworkspace.dto.request.RemoteWorkspaceUpdateRequest;
import com.theseus.api.domain.remoteworkspace.dto.response.RemoteWorkspaceConnectionTestResponse;
import com.theseus.api.domain.remoteworkspace.dto.response.RemoteWorkspaceResponse;
import com.theseus.api.domain.remoteworkspace.entity.RemoteWorkspace;
import com.theseus.api.domain.remoteworkspace.entity.RemoteWorkspaceStatus;
import com.theseus.api.domain.remoteworkspace.repository.RemoteWorkspaceRepository;
import com.theseus.api.domain.toolgeneration.event.ToolPlanRemoteWorkspacePayload;
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
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class RemoteWorkspaceService {

	private static final Duration CORE_CONNECTION_TEST_TIMEOUT = Duration.ofSeconds(15);

	private final RemoteWorkspaceRepository remoteWorkspaceRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final UserRepository userRepository;
	private final CoreStreamProperties coreStreamProperties;
	private final ObjectMapper objectMapper;
	private final HttpClient httpClient = HttpClient.newBuilder()
		.connectTimeout(Duration.ofSeconds(5))
		.build();

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
			request.getBasePath()
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
	 * Core SSH Connector 연동 전까지 연결 테스트 API의 응답 틀만 제공합니다.
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

		CoreConnectionTestResult result = requestCoreConnectionTest(remoteWorkspace);
		return RemoteWorkspaceConnectionTestResponse.createFrom(
			remoteWorkspace,
			result.available(),
			result.message()
		);
	}

	private CoreConnectionTestResult requestCoreConnectionTest(RemoteWorkspace remoteWorkspace) {
		try {
			String requestBody = objectMapper.writeValueAsString(
				ToolPlanRemoteWorkspacePayload.createFrom(remoteWorkspace)
			);
			HttpRequest request = HttpRequest.newBuilder(coreStreamProperties.remoteWorkspaceConnectionTestUri())
				.timeout(CORE_CONNECTION_TEST_TIMEOUT)
				.header(HttpHeaders.CONTENT_TYPE, MediaType.APPLICATION_JSON_VALUE)
				.POST(BodyPublishers.ofString(requestBody, StandardCharsets.UTF_8))
				.build();

			HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());
			if (response.statusCode() < 200 || response.statusCode() >= 300) {
				log.warn(">>>> Core RemoteWorkspace connection test returned non-success status. status={}",
					response.statusCode());
				return new CoreConnectionTestResult(false, "Core Remote Workspace connection test failed.");
			}

			CoreConnectionTestResult result = objectMapper.readValue(response.body(), CoreConnectionTestResult.class);
			return new CoreConnectionTestResult(
				Boolean.TRUE.equals(result.available()),
				result.message() == null || result.message().isBlank()
					? "Remote Workspace connection test completed."
					: result.message()
			);
		} catch (InterruptedException exception) {
			Thread.currentThread().interrupt();
			log.warn(">>>> Core RemoteWorkspace connection test was interrupted.", exception);
			return new CoreConnectionTestResult(false, "Core Remote Workspace connection test was interrupted.");
		} catch (IOException exception) {
			log.warn(">>>> Core RemoteWorkspace connection test request failed.", exception);
			return new CoreConnectionTestResult(false, "Core Remote Workspace connection test failed.");
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

	@JsonIgnoreProperties(ignoreUnknown = true)
	private record CoreConnectionTestResult(
		Boolean available,
		String message
	) {
	}
}
