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
import com.theseus.api.domain.tool.entity.ToolPlanRun;
import com.theseus.api.domain.tool.repository.ToolPlanRunRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ToolPlanRunAccessService {

	private final UserRepository userRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final ChatSessionRepository chatSessionRepository;
	private final ToolPlanRunRepository toolPlanRunRepository;

	/**
	 * 현재 사용자가 접근할 수 있는 ToolPlanRun인지 프로젝트 멤버십과 세션 소속을 기준으로 검증합니다.
	 */
	public ToolPlanRun getAccessibleRun(
		AuthenticatedUser currentUser,
		Long projectId,
		Long chatSessionId,
		String runId
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
		return toolPlanRunRepository.findByRunIdAndProjectAndChatSession(runId, project, chatSession)
			.orElseThrow(() -> BusinessException.of(ErrorCode.TOOL_PLAN_RUN_NOT_FOUND));
	}
}
