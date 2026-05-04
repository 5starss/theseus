package com.theseus.api.domain.chat.service;

import com.theseus.api.common.exception.CustomException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.dto.response.ChatMessageResponse;
import com.theseus.api.domain.chat.dto.request.ChatMessageCreateRequest;
import com.theseus.api.domain.chat.entity.ChatMessage;
import com.theseus.api.domain.chat.entity.ChatMessageContentType;
import com.theseus.api.domain.chat.entity.ChatMessageSenderType;
import com.theseus.api.domain.chat.entity.ChatMessageType;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.chat.repository.ChatMessageRepository;
import com.theseus.api.domain.chat.repository.ChatSessionRepository;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.util.List;
import java.util.Objects;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ChatMessageService {

	private final ChatMessageRepository chatMessageRepository;
	private final ChatSessionRepository chatSessionRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final ToolRepository toolRepository;
	private final UserRepository userRepository;

	@Transactional
	public ChatMessageResponse createUserMessage(
		AuthenticatedUser currentUser,
		Long projectId,
		Long sessionId,
		ChatMessageCreateRequest request
	) {
		ChatSession chatSession = getAccessibleChatSessionForUpdate(currentUser, projectId, sessionId);
		validateOpenChatSession(chatSession);

		ChatMessage chatMessage = saveMessage(
			chatSession,
			null,
			ChatMessageSenderType.USER,
			request.getMessageType(),
			request.getContentType(),
			request.getContent()
		);

		return ChatMessageResponse.createFrom(chatMessage);
	}

	@Transactional
	public ChatMessageResponse createInternalMessage(
		Long userId,
		Long projectId,
		Long sessionId,
		Long toolId,
		ChatMessageSenderType senderType,
		ChatMessageType messageType,
		ChatMessageContentType contentType,
		String content
	) {
		User user = getUserEntity(userId);
		ChatSession chatSession = getAccessibleChatSessionForUpdate(user, projectId, sessionId);
		validateOpenChatSession(chatSession);
		Tool tool = resolveTool(chatSession, projectId, toolId);

		ChatMessage chatMessage = saveMessage(
			chatSession,
			tool,
			senderType,
			messageType,
			contentType,
			content
		);
		return ChatMessageResponse.createFrom(chatMessage);
	}

	public List<ChatMessageResponse> getMessages(
		AuthenticatedUser currentUser,
		Long projectId,
		Long sessionId
	) {
		ChatSession chatSession = getAccessibleChatSession(currentUser, projectId, sessionId);

		return chatMessageRepository.findByChatSessionOrderByMessageOrderAsc(chatSession).stream()
			.map(ChatMessageResponse::createFrom)
			.toList();
	}

	@Transactional
	public ChatMessage saveAssistantMessage(
		ChatSession chatSession,
		Tool tool,
		ChatMessageType messageType,
		ChatMessageContentType contentType,
		String content
	) {
		return saveMessage(
			chatSession,
			tool,
			ChatMessageSenderType.ASSISTANT,
			messageType,
			contentType,
			content
		);
	}

	@Transactional
	public ChatMessage saveUserToolMessage(
		ChatSession chatSession,
		Tool tool,
		ChatMessageType messageType,
		ChatMessageContentType contentType,
		String content
	) {
		validateToolChatSession(chatSession, tool);

		return saveMessage(
			chatSession,
			tool,
			ChatMessageSenderType.USER,
			messageType,
			contentType,
			content
		);
	}

	private ChatMessage saveMessage(
		ChatSession chatSession,
		Tool tool,
		ChatMessageSenderType senderType,
		ChatMessageType messageType,
		ChatMessageContentType contentType,
		String content
	) {
		Integer nextMessageOrder = getNextMessageOrder(chatSession);
		ChatMessage chatMessage = ChatMessage.builder()
			.chatSession(chatSession)
			.tool(tool)
			.messageOrder(nextMessageOrder)
			.senderType(senderType)
			.messageType(messageType)
			.contentType(contentType)
			.content(content)
			.build();

		return chatMessageRepository.save(chatMessage);
	}

	private Integer getNextMessageOrder(ChatSession chatSession) {
		return chatMessageRepository.findTopByChatSessionOrderByMessageOrderDesc(chatSession)
			.map(chatMessage -> chatMessage.getMessageOrder() + 1)
			.orElse(1);
	}

	private void validateToolChatSession(ChatSession chatSession, Tool tool) {
		if (tool == null || !Objects.equals(tool.getChatSession().getId(), chatSession.getId())) {
			throw new CustomException(ErrorCode.TOOL_CHAT_SESSION_MISMATCH);
		}
	}

	private Tool resolveTool(ChatSession chatSession, Long projectId, Long toolId) {
		if (toolId == null) {
			return null;
		}

		Project project = getProjectEntity(projectId);
		return toolRepository.findByIdAndProjectAndChatSession(toolId, project, chatSession)
			.orElseThrow(() -> new CustomException(ErrorCode.TOOL_CHAT_SESSION_MISMATCH));
	}

	private ChatSession getAccessibleChatSession(AuthenticatedUser currentUser, Long projectId, Long sessionId) {
		User user = getCurrentUserEntity(currentUser);
		return getAccessibleChatSession(user, projectId, sessionId);
	}

	private ChatSession getAccessibleChatSession(User user, Long projectId, Long sessionId) {
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);

		return chatSessionRepository.findByIdAndProjectAndProjectMember(sessionId, project, projectMember)
			.orElseThrow(() -> new CustomException(ErrorCode.CHAT_SESSION_NOT_FOUND));
	}

	private ChatSession getAccessibleChatSessionForUpdate(AuthenticatedUser currentUser, Long projectId, Long sessionId) {
		User user = getCurrentUserEntity(currentUser);
		return getAccessibleChatSessionForUpdate(user, projectId, sessionId);
	}

	private ChatSession getAccessibleChatSessionForUpdate(User user, Long projectId, Long sessionId) {
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);

		return chatSessionRepository.findByIdAndProjectAndProjectMemberForUpdate(sessionId, project, projectMember)
			.orElseThrow(() -> new CustomException(ErrorCode.CHAT_SESSION_NOT_FOUND));
	}

	private User getCurrentUserEntity(AuthenticatedUser currentUser) {
		if (currentUser == null) {
			throw new CustomException(ErrorCode.UNAUTHORIZED);
		}

		return getUserEntity(currentUser.userId());
	}

	private User getUserEntity(Long userId) {
		return userRepository.findById(userId)
			.orElseThrow(() -> new CustomException(ErrorCode.USER_NOT_FOUND));
	}

	private Project getProjectEntity(Long projectId) {
		return projectRepository.findById(projectId)
			.orElseThrow(() -> new CustomException(ErrorCode.PROJECT_NOT_FOUND));
	}

	private ProjectMember getActiveProjectMember(Project project, User user) {
		ProjectMember projectMember = projectMemberRepository.findByProjectAndUser(project, user)
			.orElseThrow(() -> new CustomException(ErrorCode.PROJECT_MEMBER_PERMISSION_REQUIRED));

		if (!ProjectMemberStatus.IN_PROGRESS.equals(projectMember.getStatus())) {
			throw new CustomException(ErrorCode.ACTIVE_PROJECT_MEMBER_REQUIRED);
		}

		return projectMember;
	}

	private void validateOpenChatSession(ChatSession chatSession) {
		if (chatSession.isClosed()) {
			throw new CustomException(ErrorCode.CLOSED_CHAT_SESSION);
		}
	}
}
