package com.theseus.api.domain.toolgeneration.service;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.chat.repository.ChatSessionRepository;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.toolgeneration.config.ToolGenerationStateProperties;
import com.theseus.api.domain.toolgeneration.dto.ToolGenerationSseEvent;
import com.theseus.api.domain.toolgeneration.redis.ToolGenerationStateStore;
import com.theseus.api.domain.toolgeneration.sse.ToolGenerationSseEmitterRegistry;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ToolGenerationEventStreamService {

	private final UserRepository userRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final ChatSessionRepository chatSessionRepository;
	private final ToolRepository toolRepository;
	private final ToolGenerationStateStore toolGenerationStateStore;
	private final ToolGenerationStateProperties properties;
	private final ToolGenerationSseEmitterRegistry emitterRegistry;

	public SseEmitter subscribe(
		AuthenticatedUser currentUser,
		Long projectId,
		Long chatSessionId,
		Long toolId
	) {
		validateAccessibleTool(currentUser, projectId, chatSessionId, toolId);

		SseEmitter emitter = new SseEmitter(properties.sseTimeoutMillis());
		emitterRegistry.register(projectId, chatSessionId, toolId, emitter);
		emitterRegistry.sendToEmitter(
			projectId,
			chatSessionId,
			toolId,
			emitter,
			ToolGenerationSseEvent.connectedOf(projectId, chatSessionId, toolId)
		);
		toolGenerationStateStore.findByToolId(toolId)
			.ifPresent(state -> emitterRegistry.sendToEmitter(
				projectId,
				chatSessionId,
				toolId,
				emitter,
				ToolGenerationSseEvent.createFrom(state)
			));

		return emitter;
	}

	private void validateAccessibleTool(
		AuthenticatedUser currentUser,
		Long projectId,
		Long chatSessionId,
		Long toolId
	) {
		if (currentUser == null) {
			throw BusinessException.of(ErrorCode.UNAUTHORIZED);
		}

		User user = userRepository.findById(currentUser.userId())
			.orElseThrow(() -> BusinessException.of(ErrorCode.USER_NOT_FOUND));
		Project project = projectRepository.findById(projectId)
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_NOT_FOUND));
		ProjectMember projectMember = projectMemberRepository.findByProjectAndUser(project, user)
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_MEMBER_PERMISSION_REQUIRED));

		if (!ProjectMemberStatus.IN_PROGRESS.equals(projectMember.getStatus())) {
			throw BusinessException.of(ErrorCode.ACTIVE_PROJECT_MEMBER_REQUIRED);
		}

		ChatSession chatSession = chatSessionRepository.findByIdAndProject(chatSessionId, project)
			.orElseThrow(() -> BusinessException.of(ErrorCode.CHAT_SESSION_NOT_FOUND));
		toolRepository.findByIdAndProjectAndChatSession(toolId, project, chatSession)
			.orElseThrow(() -> BusinessException.of(ErrorCode.TOOL_CHAT_SESSION_MISMATCH));
	}
}
