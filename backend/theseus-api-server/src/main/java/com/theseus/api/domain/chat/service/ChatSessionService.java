package com.theseus.api.domain.chat.service;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
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
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ChatSessionService {

	private final ChatSessionRepository chatSessionRepository;
	private final ChatMessageRepository chatMessageRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final UserRepository userRepository;

	/**
	 * 로그인 사용자의 프로젝트 멤버 권한으로 새 채팅 세션을 생성합니다.
	 */
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

	/**
	 * 로그인 사용자가 접근 가능한 프로젝트의 채팅 세션 목록을 조회합니다.
	 */
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

	/**
	 * 채팅 세션 상세 정보와 세션 메시지 목록을 함께 조회합니다.
	 */
	public ChatSessionDetailResponse getChatSession(
		AuthenticatedUser currentUser,
		Long projectId,
		Long sessionId
	) {
		ChatSession chatSession = getAccessibleChatSession(currentUser, projectId, sessionId);
		List<ChatMessage> messages = chatMessageRepository.findByChatSessionOrderByMessageOrderAsc(chatSession);

		return ChatSessionDetailResponse.createOf(chatSession, messages);
	}

	/**
	 * 접근 가능한 채팅 세션의 제목을 수정합니다.
	 */
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

	/**
	 * 접근 가능한 채팅 세션을 종료 처리합니다.
	 */
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
			.orElseThrow(() -> BusinessException.of(ErrorCode.CHAT_SESSION_NOT_FOUND));
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

	private Pageable createPageable(int page, int size) {
		return PageRequest.of(Math.max(page, 0), Math.max(size, 1));
	}
}
