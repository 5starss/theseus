package com.theseus.api.domain.chat.service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.config.CoreStreamProperties;
import com.theseus.api.domain.chat.dto.request.ChatStreamRequest;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.chat.repository.ChatSessionRepository;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.remoteworkspace.entity.RemoteWorkspaceStatus;
import com.theseus.api.domain.remoteworkspace.repository.RemoteWorkspaceRepository;
import com.theseus.api.domain.tool.entity.ToolPlanMode;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Map;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.servlet.mvc.method.annotation.StreamingResponseBody;

@Slf4j
@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ChatStreamService {

	private static final Duration CORE_STREAM_TIMEOUT = Duration.ofMinutes(30);

	private final CoreStreamProperties coreStreamProperties;
	private final UserRepository userRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final ChatSessionRepository chatSessionRepository;
	private final RemoteWorkspaceRepository remoteWorkspaceRepository;
	private final ObjectMapper objectMapper;
	private final HttpClient httpClient = HttpClient.newBuilder()
		.connectTimeout(Duration.ofSeconds(5))
		.build();

	/**
	 * ASK/AGENT 채팅 요청을 검증하고 Core SSE 스트림을 그대로 프록시합니다.
	 */
	public StreamingResponseBody streamChat(
		AuthenticatedUser currentUser,
		Long projectId,
		Long sessionId,
		ChatStreamRequest request,
		String authorizationHeader
	) {
		validateAuthorizationHeader(authorizationHeader);
		validateStreamMode(request.getMode());
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);
		ChatSession chatSession = getAccessibleChatSession(sessionId, project, projectMember);
		validateOpenChatSession(chatSession);
		validateAgentModePermission(request.getMode(), projectMember);
		validateRemoteWorkspace(project, request.getRemoteWorkspaceId());

		return outputStream -> proxyCoreStream(
			outputStream,
			projectId,
			sessionId,
			request,
			authorizationHeader
		);
	}

	private void proxyCoreStream(
		OutputStream outputStream,
		Long projectId,
		Long sessionId,
		ChatStreamRequest request,
		String authorizationHeader
	) throws IOException {
		HttpRequest coreRequest = HttpRequest.newBuilder(
				coreStreamProperties.streamUri(
					request.getPrompt(),
					projectId,
					sessionId,
					request.getMode(),
					request.getRemoteWorkspaceId()
				)
			)
			.timeout(CORE_STREAM_TIMEOUT)
			.header(HttpHeaders.ACCEPT, MediaType.TEXT_EVENT_STREAM_VALUE)
			.header(HttpHeaders.AUTHORIZATION, authorizationHeader)
			.GET()
			.build();

		try {
			HttpResponse<InputStream> response = httpClient.send(coreRequest, HttpResponse.BodyHandlers.ofInputStream());
			if (response.statusCode() < 200 || response.statusCode() >= 300) {
				log.warn(">>>> Core chat stream returned non-success status. status={}", response.statusCode());
				writeSseEvent(
					outputStream,
					"error",
					Map.of("message", "Core chat stream request failed.", "status", response.statusCode())
				);
				return;
			}

			try (InputStream body = response.body()) {
				body.transferTo(outputStream);
				outputStream.flush();
			}
		} catch (InterruptedException exception) {
			Thread.currentThread().interrupt();
			log.warn(">>>> Core chat stream proxy was interrupted.", exception);
			writeSseEvent(outputStream, "error", Map.of("message", "Core chat stream was interrupted."));
		} catch (IOException exception) {
			log.warn(">>>> Core chat stream proxy failed.", exception);
			writeSseEvent(outputStream, "error", Map.of("message", "Core chat stream connection failed."));
		}
	}

	private void writeSseEvent(OutputStream outputStream, String eventType, Map<String, Object> data) throws IOException {
		String payload = "event: " + eventType + "\n"
			+ "data: " + objectMapper.writeValueAsString(data) + "\n\n";
		outputStream.write(payload.getBytes(StandardCharsets.UTF_8));
		outputStream.flush();
	}

	private void validateStreamMode(ToolPlanMode mode) {
		if (!ToolPlanMode.ASK.equals(mode) && !ToolPlanMode.AGENT.equals(mode)) {
			throw BusinessException.of(ErrorCode.CHAT_STREAM_MODE_INVALID);
		}
	}

	private void validateAgentModePermission(ToolPlanMode mode, ProjectMember projectMember) {
		if (ToolPlanMode.AGENT.equals(mode) && !Boolean.TRUE.equals(projectMember.getCanUseTool())) {
			throw BusinessException.of(ErrorCode.TOOL_USE_PERMISSION_REQUIRED);
		}
	}

	private void validateAuthorizationHeader(String authorizationHeader) {
		if (authorizationHeader == null || authorizationHeader.isBlank()) {
			throw BusinessException.of(ErrorCode.UNAUTHORIZED);
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

	private ChatSession getAccessibleChatSession(Long sessionId, Project project, ProjectMember projectMember) {
		return chatSessionRepository.findByIdAndProjectAndProjectMember(sessionId, project, projectMember)
			.orElseThrow(() -> BusinessException.of(ErrorCode.CHAT_SESSION_NOT_FOUND));
	}

	private void validateOpenChatSession(ChatSession chatSession) {
		if (chatSession.isClosed()) {
			throw BusinessException.of(ErrorCode.CLOSED_CHAT_SESSION);
		}
	}

	private void validateRemoteWorkspace(Project project, Long remoteWorkspaceId) {
		if (remoteWorkspaceId == null) {
			return;
		}

		remoteWorkspaceRepository.findByIdAndProjectAndStatusNot(
			remoteWorkspaceId,
			project,
			RemoteWorkspaceStatus.DELETED
		).orElseThrow(() -> BusinessException.of(ErrorCode.REMOTE_WORKSPACE_NOT_FOUND));
	}
}
