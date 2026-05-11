package com.theseus.api.domain.tool.service;

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
import com.theseus.api.domain.tool.dto.response.ToolPlanDetailResponse;
import com.theseus.api.domain.tool.entity.ToolPlan;
import com.theseus.api.domain.tool.repository.ToolPlanRepository;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ToolPlanQueryService {

	private final UserRepository userRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final ChatSessionRepository chatSessionRepository;
	private final ToolPlanRepository toolPlanRepository;

	/**
	 * 프로젝트 멤버 권한과 세션 소속을 검증한 뒤 ToolPlan 상세 정보를 조회합니다.
	 */
	public ToolPlanDetailResponse getToolPlanDetail(
		AuthenticatedUser currentUser,
		Long projectId,
		Long chatSessionId,
		Long toolPlanId
	) {
		validateAuthenticatedUser(currentUser);

		User user = userRepository.findById(currentUser.userId())
			.orElseThrow(() -> BusinessException.of(ErrorCode.USER_NOT_FOUND));
		Project project = projectRepository.findById(projectId)
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_NOT_FOUND));
		validateActiveProjectMember(project, user);

		ChatSession chatSession = chatSessionRepository.findByIdAndProject(chatSessionId, project)
			.orElseThrow(() -> BusinessException.of(ErrorCode.CHAT_SESSION_NOT_FOUND));
		ToolPlan toolPlan = toolPlanRepository.findByIdAndProjectAndChatSession(toolPlanId, project, chatSession)
			.orElseThrow(() -> BusinessException.of(ErrorCode.TOOL_PLAN_NOT_FOUND));

		return ToolPlanDetailResponse.createFrom(toolPlan);
	}

	private void validateAuthenticatedUser(AuthenticatedUser currentUser) {
		if (currentUser == null) {
			throw BusinessException.of(ErrorCode.UNAUTHORIZED);
		}
	}

	private void validateActiveProjectMember(Project project, User user) {
		ProjectMember projectMember = projectMemberRepository.findByProjectAndUser(project, user)
			.orElseThrow(() -> BusinessException.of(ErrorCode.PROJECT_MEMBER_PERMISSION_REQUIRED));
		if (!ProjectMemberStatus.IN_PROGRESS.equals(projectMember.getStatus())) {
			throw BusinessException.of(ErrorCode.ACTIVE_PROJECT_MEMBER_REQUIRED);
		}
	}
}
