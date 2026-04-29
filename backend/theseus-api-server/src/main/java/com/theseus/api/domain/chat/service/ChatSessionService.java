package com.theseus.api.domain.chat.service;

import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.dto.request.ChatSessionCreateRequest;
import com.theseus.api.domain.chat.dto.request.ChatSessionUpdateRequest;
import com.theseus.api.domain.chat.dto.response.ChatSessionDetailResponse;
import com.theseus.api.domain.chat.dto.response.ChatSessionResponse;
import com.theseus.api.domain.chat.entity.ChatMessage;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.chat.repository.ChatMessageRepository;
import com.theseus.api.domain.chat.repository.ChatSessionRepository;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.time.LocalDateTime;
import java.util.List;
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
public class ChatSessionService {

	private final ChatSessionRepository chatSessionRepository;
	private final ChatMessageRepository chatMessageRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final UserRepository userRepository;

	@Transactional
	public ChatSessionResponse createChatSession(
		AuthenticatedUser currentUser,
		Long projectId,
		ChatSessionCreateRequest request
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);

		ChatSession chatSession = chatSessionRepository.save(request.toEntity(project, projectMember));

		return ChatSessionResponse.createFrom(chatSession);
	}

	public Page<ChatSessionResponse> getChatSessions(
		AuthenticatedUser currentUser,
		Long projectId,
		int page,
		int size
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);
		Pageable pageable = createPageable(page, size);

		return chatSessionRepository.findByProjectAndProjectMemberOrderByUpdatedAtDesc(project, projectMember, pageable)
			.map(ChatSessionResponse::createFrom);
	}

	public ChatSessionDetailResponse getChatSession(
		AuthenticatedUser currentUser,
		Long projectId,
		Long sessionId
	) {
		ChatSession chatSession = getAccessibleChatSession(currentUser, projectId, sessionId);
		List<ChatMessage> messages = chatMessageRepository.findByChatSessionOrderByMessageOrderAsc(chatSession);

		return ChatSessionDetailResponse.createOf(chatSession, messages);
	}

	@Transactional
	public ChatSessionResponse updateChatSessionTitle(
		AuthenticatedUser currentUser,
		Long projectId,
		Long sessionId,
		ChatSessionUpdateRequest request
	) {
		ChatSession chatSession = getAccessibleChatSession(currentUser, projectId, sessionId);

		chatSession.updateTitle(request.getTitle());

		return ChatSessionResponse.createFrom(chatSession);
	}

	@Transactional
	public ChatSessionResponse closeChatSession(
		AuthenticatedUser currentUser,
		Long projectId,
		Long sessionId
	) {
		ChatSession chatSession = getAccessibleChatSession(currentUser, projectId, sessionId);

		if (!chatSession.isClosed()) {
			chatSession.close(LocalDateTime.now());
		}

		return ChatSessionResponse.createFrom(chatSession);
	}

	private ChatSession getAccessibleChatSession(AuthenticatedUser currentUser, Long projectId, Long sessionId) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);

		return chatSessionRepository.findByIdAndProjectAndProjectMember(sessionId, project, projectMember)
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

	private Pageable createPageable(int page, int size) {
		return PageRequest.of(Math.max(page, 0), Math.max(size, 1));
	}
}
