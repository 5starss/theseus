package com.theseus.api.domain.chat.service;

import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.dto.request.ChatMessageCreateRequest;
import com.theseus.api.domain.chat.dto.response.ChatMessageResponse;
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
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ChatMessageService {

	private final ChatMessageRepository chatMessageRepository;
	private final ChatSessionRepository chatSessionRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
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

	private ChatSession getAccessibleChatSession(AuthenticatedUser currentUser, Long projectId, Long sessionId) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);

		return chatSessionRepository.findByIdAndProjectAndProjectMember(sessionId, project, projectMember)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "채팅 세션을 찾을 수 없습니다."));
	}

	private ChatSession getAccessibleChatSessionForUpdate(AuthenticatedUser currentUser, Long projectId, Long sessionId) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);

		return chatSessionRepository.findByIdAndProjectAndProjectMemberForUpdate(sessionId, project, projectMember)
			.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "채팅 세션을 찾을 수 없습니다."));
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

	private void validateOpenChatSession(ChatSession chatSession) {
		if (chatSession.isClosed()) {
			throw new ResponseStatusException(HttpStatus.CONFLICT, "종료된 채팅 세션에는 메시지를 등록할 수 없습니다.");
		}
	}
}
