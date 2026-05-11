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
@Tag(name = "ChatSession", description = "ChatSession API")
@RequestMapping("/api/v1/projects/{projectId}/sessions")
public class ChatSessionController {

	private final ChatSessionService chatSessionService;

	@Operation(summary = "ChatSession create", description = "Creates a chat session for a project member.")
	@PostMapping
	public ResponseEntity<ApiResponse<ChatSessionResponse>> createChatSession(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@Valid @RequestBody ChatSessionCreateRequest request
	) {
		ChatSessionResponse response = chatSessionService.createChatSession(currentUser, projectId, request);
		return ApiResponse.onSuccess(SuccessCode.CREATED, response);
	}

	@Operation(summary = "ChatSession list", description = "Returns accessible chat sessions for the project member.")
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

	@Operation(summary = "ChatSession detail", description = "Returns a chat session and ordered messages.")
	@GetMapping("/{sessionId}")
	public ResponseEntity<ApiResponse<ChatSessionDetailResponse>> getChatSession(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long sessionId
	) {
		ChatSessionDetailResponse response = chatSessionService.getChatSession(currentUser, projectId, sessionId);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}

	@Operation(summary = "ChatSession title update", description = "Updates a chat session title.")
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

	@Operation(summary = "ChatSession close", description = "Closes a chat session and records closedAt.")
	@PatchMapping("/{sessionId}/close")
	public ResponseEntity<ApiResponse<ChatSessionResponse>> closeChatSession(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long sessionId
	) {
		ChatSessionResponse response = chatSessionService.closeChatSession(currentUser, projectId, sessionId);
		return ApiResponse.onSuccess(SuccessCode.OK, response);
	}
}
