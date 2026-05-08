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
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.toolgeneration.dto.response.ToolGenerationStateResponse;
import com.theseus.api.domain.toolgeneration.redis.ToolGenerationStateStore;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ToolGenerationStateService {

	private final UserRepository userRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final ChatSessionRepository chatSessionRepository;
	private final ToolRepository toolRepository;
	private final ToolGenerationStateStore toolGenerationStateStore;

	/**
	 * Redis 최신 상태를 우선 조회하고, 없으면 DB Tool 상태로 생성 진행 상태를 복구합니다.
	 */
	public ToolGenerationStateResponse getToolGenerationState(
		AuthenticatedUser currentUser,
		Long projectId,
		Long chatSessionId,
		Long toolId
	) {
		Tool tool = getAccessibleTool(currentUser, projectId, chatSessionId, toolId);

		try {
			return toolGenerationStateStore.findByToolId(toolId)
				.map(ToolGenerationStateResponse::createFrom)
				.orElseGet(() -> ToolGenerationStateResponse.createFallbackFrom(tool));
		} catch (RuntimeException exception) {
			log.warn(
				">>>> Failed to find Tool generation Redis state. projectId={}, chatSessionId={}, toolId={}",
				projectId,
				chatSessionId,
				toolId,
				exception
			);
			return ToolGenerationStateResponse.createFallbackFrom(tool);
		}
	}

	private Tool getAccessibleTool(
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
		return toolRepository.findByIdAndProjectAndChatSession(toolId, project, chatSession)
			.orElseThrow(() -> BusinessException.of(ErrorCode.TOOL_CHAT_SESSION_MISMATCH));
	}
}
