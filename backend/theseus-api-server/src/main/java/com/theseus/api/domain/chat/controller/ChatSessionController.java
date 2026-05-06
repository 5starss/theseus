package com.theseus.api.domain.chat.controller;

import com.theseus.api.common.response.ApiResponse;
import com.theseus.api.common.response.status.SuccessCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.dto.request.ChatSessionCreateRequest;
import com.theseus.api.domain.chat.dto.request.ChatSessionUpdateRequest;
import com.theseus.api.domain.chat.dto.response.ChatSessionDetailResponse;
import com.theseus.api.domain.chat.dto.response.ChatSessionPageResponse;
import com.theseus.api.domain.chat.dto.response.ChatSessionResponse;
import com.theseus.api.domain.chat.service.ChatSessionService;
import com.theseus.api.domain.toolgeneration.dto.request.ToolGenerationRequest;
import com.theseus.api.domain.toolgeneration.dto.request.ToolRegenerationRequest;
import com.theseus.api.domain.toolgeneration.dto.response.ToolGenerationRunResponse;
import com.theseus.api.domain.toolgeneration.service.ToolGenerationService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.data.domain.Page;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@Tag(name = "ChatSession", description = "채팅 세션 관리 API")
@RequestMapping("/api/v1/projects/{projectId}/sessions")
public class ChatSessionController {

	private final ChatSessionService chatSessionService;
	private final ToolGenerationService toolGenerationService;

	@Operation(summary = "채팅 세션 생성", description = "프로젝트 멤버가 Tool 생성을 진행할 채팅 세션을 생성합니다.")
	@PostMapping
	public ResponseEntity<ApiResponse<ChatSessionResponse>> createChatSession(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@Valid @RequestBody ChatSessionCreateRequest request
	) {
		ChatSessionResponse response = chatSessionService.createChatSession(currentUser, projectId, request);
		return ApiResponse.onSuccess(SuccessCode.CREATED, response);
	}

	@Operation(summary = "채팅 세션 목록 조회", description = "로그인한 프로젝트 멤버가 본인이 생성한 채팅 세션 목록을 조회합니다.")
	@GetMapping
	public ResponseEntity<ApiResponse<ChatSessionPageResponse<ChatSessionResponse>>> getChatSessions(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@RequestParam(defaultValue = "0") int page,
		@RequestParam(defaultValue = "20") int size
	) {
		Page<ChatSessionResponse> chatSessions = chatSessionService.getChatSessions(currentUser, projectId, page, size);
		return ApiResponse.onSuccess(SuccessCode.OK, ChatSessionPageResponse.createFrom(chatSessions));
	}

	@Operation(summary = "채팅 세션 상세 조회", description = "채팅 세션 정보와 messageOrder 오름차순 메시지 목록을 조회합니다.")
	@GetMapping("/{sessionId}")
	public ResponseEntity<ApiResponse<ChatSessionDetailResponse>> getChatSession(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long sessionId
	) {
		ChatSessionDetailResponse response = chatSessionService.getChatSession(currentUser, projectId, sessionId);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}

	@Operation(summary = "채팅 세션 제목 수정", description = "로그인한 프로젝트 멤버가 본인이 생성한 채팅 세션의 제목을 수정합니다.")
	@PatchMapping("/{sessionId}")
	public ResponseEntity<ApiResponse<ChatSessionResponse>> updateChatSessionTitle(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long sessionId,
		@Valid @RequestBody ChatSessionUpdateRequest request
	) {
		ChatSessionResponse response = chatSessionService.updateChatSessionTitle(currentUser, projectId, sessionId, request);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}

	@Operation(summary = "채팅 세션 종료", description = "채팅 세션을 종료하고 closedAt을 기록합니다.")
	@PatchMapping("/{sessionId}/close")
	public ResponseEntity<ApiResponse<ChatSessionResponse>> closeChatSession(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long sessionId
	) {
		ChatSessionResponse response = chatSessionService.closeChatSession(currentUser, projectId, sessionId);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}

	@Operation(summary = "Draft Tool 생성 요청", description = "채팅 세션 기반 Draft Tool을 생성하고 Kafka에 생성 요청을 발행합니다.")
	@PostMapping("/{sessionId}/tools/generate")
	public ResponseEntity<ApiResponse<ToolGenerationRunResponse>> generateTool(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long sessionId,
		@Valid @RequestBody ToolGenerationRequest request
	) {
		ToolGenerationRunResponse response = toolGenerationService.generateTool(
			currentUser,
			projectId,
			sessionId,
			request
		);
		return ApiResponse.onSuccess(SuccessCode.ACCEPTED, response);
	}

	@Operation(summary = "Draft Tool 재생성 요청", description = "채팅 세션의 기존 Draft Tool을 PLAN 단계로 되돌리고 Kafka에 재생성 요청을 발행합니다.")
	@PatchMapping("/{sessionId}/tools/{toolId}/regenerate")
	public ResponseEntity<ApiResponse<ToolGenerationRunResponse>> regenerateTool(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long sessionId,
		@PathVariable Long toolId,
		@Valid @RequestBody ToolRegenerationRequest request
	) {
		ToolGenerationRunResponse response = toolGenerationService.regenerateTool(
			currentUser,
			projectId,
			sessionId,
			toolId,
			request
		);
		return ApiResponse.onSuccess(SuccessCode.ACCEPTED, response);
	}
}
