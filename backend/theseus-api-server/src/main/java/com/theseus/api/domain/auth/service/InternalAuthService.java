package com.theseus.api.domain.auth.service;

import com.theseus.api.common.exception.BusinessException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.dto.request.InternalAuthVerifyRequest;
import com.theseus.api.domain.auth.dto.response.InternalAuthVerifyResponse;
import com.theseus.api.domain.auth.token.JwtTokenProvider;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.chat.repository.ChatSessionRepository;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.entity.UserStatus;
import com.theseus.api.domain.user.repository.UserRepository;
import io.jsonwebtoken.JwtException;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class InternalAuthService {

	private static final int DEFAULT_PERMISSION_LEVEL = 1;
	private static final int SUPER_ADMIN_PERMISSION_LEVEL = 3;

	private final JwtTokenProvider jwtTokenProvider;
	private final UserRepository userRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final ChatSessionRepository chatSessionRepository;

	public InternalAuthVerifyResponse verify(InternalAuthVerifyRequest request) {
		User user = getUserFromToken(request.getToken());
		validateActiveUser(user);

		ProjectContext projectContext = resolveProjectContext(user, request);

		return InternalAuthVerifyResponse.builder()
			.userId(String.valueOf(user.getId()))
			.projectId(projectContext.projectId())
			.permissionLevel(projectContext.permissionLevel())
			.build();
	}

	private User getUserFromToken(String token) {
		try {
			jwtTokenProvider.validateAccessToken(token);
			Long userId = jwtTokenProvider.getUserId(token);

			return userRepository.findById(userId)
				.orElseThrow(() -> BusinessException.of(ErrorCode.USER_NOT_FOUND));
		} catch (JwtException | IllegalArgumentException | BusinessException exception) {
			throw BusinessException.of(ErrorCode.UNAUTHORIZED, exception);
		}
	}

	private void validateActiveUser(User user) {
		if (!UserStatus.ACTIVE.equals(user.getStatus())) {
			throw BusinessException.of(ErrorCode.UNAUTHORIZED);
		}
	}

	private ProjectContext resolveProjectContext(User user, InternalAuthVerifyRequest request) {
		if (request.getChatSessionId() != null) {
			return resolveProjectContextByChatSession(user, request);
		}

		if (request.getProjectId() != null) {
			return resolveProjectContextByProject(user, request.getProjectId());
		}

		return new ProjectContext(
			"",
			user.isSuperAdmin() ? SUPER_ADMIN_PERMISSION_LEVEL : DEFAULT_PERMISSION_LEVEL
		);
	}

	private ProjectContext resolveProjectContextByChatSession(User user, InternalAuthVerifyRequest request) {
		ChatSession chatSession = chatSessionRepository.findById(request.getChatSessionId())
			.orElseThrow(() -> BusinessException.of(ErrorCode.CHAT_SESSION_NOT_FOUND));
		ProjectMember projectMember = chatSession.getProjectMember();

		if (!projectMember.getUser().getId().equals(user.getId())) {
			throw BusinessException.of(ErrorCode.PROJECT_MEMBER_PERMISSION_REQUIRED);
		}

		if (request.getProjectId() != null && !chatSession.getProject().getId().equals(request.getProjectId())) {
			throw BusinessException.of(ErrorCode.PROJECT_MEMBER_PERMISSION_REQUIRED);
		}

		validateActiveProjectMember(projectMember);

		return new ProjectContext(
			String.valueOf(chatSession.getProject().getId()),
			projectMember.getAccessLevel()
		);
	}

	private ProjectContext resolveProjectContextByProject(User user, Long projectId) {
		Project project = projectRepository.findById(projectId)
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_NOT_FOUND));
		ProjectMember projectMember = projectMemberRepository.findByProjectAndUser(project, user)
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_MEMBER_PERMISSION_REQUIRED));

		validateActiveProjectMember(projectMember);

		return new ProjectContext(String.valueOf(project.getId()), projectMember.getAccessLevel());
	}

	private void validateActiveProjectMember(ProjectMember projectMember) {
		if (!ProjectMemberStatus.IN_PROGRESS.equals(projectMember.getStatus())) {
			throw BusinessException.of(ErrorCode.ACTIVE_PROJECT_MEMBER_REQUIRED);
		}
	}

	private record ProjectContext(String projectId, Integer permissionLevel) {
	}
}
