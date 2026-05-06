package com.theseus.api.domain.toolgeneration.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.theseus.api.common.exception.CustomException;
import com.theseus.api.common.exception.ErrorCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.entity.ChatMessageContentType;
import com.theseus.api.domain.chat.entity.ChatMessageType;
import com.theseus.api.domain.chat.entity.ChatSession;
import com.theseus.api.domain.chat.repository.ChatSessionRepository;
import com.theseus.api.domain.chat.service.ChatMessageService;
import com.theseus.api.domain.project.entity.Project;
import com.theseus.api.domain.project.entity.ProjectMember;
import com.theseus.api.domain.project.entity.ProjectMemberStatus;
import com.theseus.api.domain.project.repository.ProjectMemberRepository;
import com.theseus.api.domain.project.repository.ProjectRepository;
import com.theseus.api.domain.tool.entity.Tool;
import com.theseus.api.domain.tool.entity.ToolStatus;
import com.theseus.api.domain.tool.repository.ToolRepository;
import com.theseus.api.domain.toolgeneration.dto.request.ToolGenerationRequest;
import com.theseus.api.domain.toolgeneration.dto.request.ToolRegenerationRequest;
import com.theseus.api.domain.toolgeneration.dto.response.ToolGenerationRunResponse;
import com.theseus.api.domain.toolgeneration.event.ToolGenerationKafkaPublishEvent;
import com.theseus.api.domain.toolgeneration.event.ToolGenerationRequestEvent;
import com.theseus.api.domain.toolgeneration.event.ToolPermissionPayload;
import com.theseus.api.domain.toolgeneration.event.ToolRegenerationRequestEvent;
import com.theseus.api.domain.user.entity.User;
import com.theseus.api.domain.user.repository.UserRepository;
import java.time.LocalDateTime;
import java.util.UUID;
import lombok.RequiredArgsConstructor;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@RequiredArgsConstructor
@Transactional(readOnly = true)
@Service
public class ToolGenerationService {

	private static final String TOOL_GENERATION_REQUESTED = "TOOL_GENERATION_REQUESTED";
	private static final String TOOL_REGENERATION_REQUESTED = "TOOL_REGENERATION_REQUESTED";

	private final ToolRepository toolRepository;
	private final ChatSessionRepository chatSessionRepository;
	private final ProjectRepository projectRepository;
	private final ProjectMemberRepository projectMemberRepository;
	private final UserRepository userRepository;
	private final ChatMessageService chatMessageService;
	private final ApplicationEventPublisher eventPublisher;
	private final ObjectMapper objectMapper;

	@Transactional
	public ToolGenerationRunResponse generateTool(
		AuthenticatedUser currentUser,
		Long projectId,
		Long sessionId,
		ToolGenerationRequest request
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);
		validateToolCreatePermission(projectMember);
		validateUniqueFileName(project, request.getFileName());

		ChatSession chatSession = getAccessibleChatSessionForUpdate(sessionId, project, projectMember);
		validateOpenChatSession(chatSession);

		Tool tool = toolRepository.save(Tool.builder()
			.project(project)
			.chatSession(chatSession)
			.createdByProjectMember(projectMember)
			.fileName(request.getFileName())
			.build());

		chatMessageService.saveUserToolMessage(
			chatSession,
			tool,
			ChatMessageType.TOOL_DRAFT_REQUEST,
			ChatMessageContentType.TEXT,
			request.getUserMessage()
		);

		String runId = createRunId();
		eventPublisher.publishEvent(new ToolGenerationKafkaPublishEvent(
			runId,
			createGenerationEvent(runId, project, chatSession, tool, projectMember, request),
			false
		));

		return ToolGenerationRunResponse.createOf(runId, tool);
	}

	@Transactional
	public ToolGenerationRunResponse regenerateTool(
		AuthenticatedUser currentUser,
		Long projectId,
		Long sessionId,
		Long toolId,
		ToolRegenerationRequest request
	) {
		User user = getCurrentUserEntity(currentUser);
		Project project = getProjectEntity(projectId);
		ProjectMember projectMember = getActiveProjectMember(project, user);

		ChatSession chatSession = getAccessibleChatSessionForUpdate(sessionId, project, projectMember);
		validateOpenChatSession(chatSession);

		Tool tool = getToolForUpdate(toolId, project, chatSession);
		validateRegenerationPermission(projectMember, tool);
		validateRegeneratableTool(tool);
		tool.startRegeneration();

		chatMessageService.saveUserToolMessage(
			chatSession,
			tool,
			ChatMessageType.TOOL_FEEDBACK,
			ChatMessageContentType.JSON,
			writeAsJson(request)
		);

		String runId = createRunId();
		eventPublisher.publishEvent(new ToolGenerationKafkaPublishEvent(
			runId,
			createRegenerationEvent(runId, project, chatSession, tool, projectMember, request),
			true
		));

		return ToolGenerationRunResponse.createOf(runId, tool);
	}

	private ToolGenerationRequestEvent createGenerationEvent(
		String runId,
		Project project,
		ChatSession chatSession,
		Tool tool,
		ProjectMember projectMember,
		ToolGenerationRequest request
	) {
		return new ToolGenerationRequestEvent(
			TOOL_GENERATION_REQUESTED,
			runId,
			project.getId(),
			chatSession.getId(),
			tool.getId(),
			projectMember.getUser().getId(),
			projectMember.getId(),
			request.getUserMessage(),
			tool.getFileName(),
			projectMember.getProjectRole(),
			createPermissionPayload(projectMember),
			LocalDateTime.now()
		);
	}

	private ToolRegenerationRequestEvent createRegenerationEvent(
		String runId,
		Project project,
		ChatSession chatSession,
		Tool tool,
		ProjectMember projectMember,
		ToolRegenerationRequest request
	) {
		return new ToolRegenerationRequestEvent(
			TOOL_REGENERATION_REQUESTED,
			runId,
			project.getId(),
			chatSession.getId(),
			tool.getId(),
			projectMember.getUser().getId(),
			projectMember.getId(),
			request.getBaseDraftVersion(),
			request.getFeedbackItems(),
			projectMember.getProjectRole(),
			createPermissionPayload(projectMember),
			LocalDateTime.now()
		);
	}

	private ToolPermissionPayload createPermissionPayload(ProjectMember projectMember) {
		return new ToolPermissionPayload(
			projectMember.getCanCreateTool(),
			projectMember.getCanUseTool(),
			projectMember.getCanUpdateTool(),
			projectMember.getCanDeleteTool()
		);
	}

	private User getCurrentUserEntity(AuthenticatedUser currentUser) {
		if (currentUser == null) {
			throw new CustomException(ErrorCode.UNAUTHORIZED);
		}

		return userRepository.findById(currentUser.userId())
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

	private ChatSession getAccessibleChatSessionForUpdate(
		Long sessionId,
		Project project,
		ProjectMember projectMember
	) {
		return chatSessionRepository.findByIdAndProjectAndProjectMemberForUpdate(sessionId, project, projectMember)
			.orElseThrow(() -> new CustomException(ErrorCode.CHAT_SESSION_NOT_FOUND));
	}

	private Tool getToolForUpdate(Long toolId, Project project, ChatSession chatSession) {
		return toolRepository.findByIdAndProjectAndChatSessionForUpdate(toolId, project, chatSession)
			.orElseThrow(() -> new CustomException(ErrorCode.TOOL_CHAT_SESSION_MISMATCH));
	}

	private void validateOpenChatSession(ChatSession chatSession) {
		if (chatSession.isClosed()) {
			throw new CustomException(ErrorCode.CLOSED_CHAT_SESSION);
		}
	}

	private void validateToolCreatePermission(ProjectMember projectMember) {
		if (!Boolean.TRUE.equals(projectMember.getCanCreateTool())) {
			throw new CustomException(ErrorCode.TOOL_CREATE_PERMISSION_REQUIRED);
		}
	}

	private void validateRegenerationPermission(ProjectMember projectMember, Tool tool) {
		boolean isCreator = tool.getCreatedByProjectMember().getId().equals(projectMember.getId());
		if (!isCreator && !Boolean.TRUE.equals(projectMember.getCanUpdateTool())) {
			throw new CustomException(ErrorCode.TOOL_UPDATE_PERMISSION_REQUIRED);
		}
	}

	private void validateUniqueFileName(Project project, String fileName) {
		if (toolRepository.existsByProjectAndFileName(project, fileName)) {
			throw new CustomException(ErrorCode.DUPLICATE_TOOL_FILE_NAME);
		}
	}

	private void validateRegeneratableTool(Tool tool) {
		if (!tool.canRegenerate() || ToolStatus.DELETED.equals(tool.getStatus())) {
			throw new CustomException(ErrorCode.TOOL_REGENERATION_STATUS_REQUIRED);
		}
	}

	private String writeAsJson(ToolRegenerationRequest request) {
		try {
			return objectMapper.writeValueAsString(request);
		} catch (JsonProcessingException exception) {
			throw new CustomException(ErrorCode.INVALID_INPUT_VALUE);
		}
	}

	private String createRunId() {
		return UUID.randomUUID().toString();
	}
}
