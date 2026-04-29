package com.theseus.api.domain.chat.controller;

import com.theseus.api.common.response.ApiResponse;
import com.theseus.api.common.response.status.SuccessCode;
import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.chat.dto.request.ChatMessageCreateRequest;
import com.theseus.api.domain.chat.dto.response.ChatMessageResponse;
import com.theseus.api.domain.chat.service.ChatMessageService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import java.util.List;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@Tag(name = "ChatMessage", description = "채팅 메시지 관리 API")
@RequestMapping("/api/v1/projects/{projectId}/sessions/{sessionId}/messages")
public class ChatMessageController {

	private final ChatMessageService chatMessageService;

	@Operation(summary = "채팅 메시지 등록", description = "로그인한 프로젝트 멤버가 본인이 생성한 채팅 세션에 USER 메시지를 등록합니다.")
	@PostMapping
	public ResponseEntity<ApiResponse<ChatMessageResponse>> createMessage(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long sessionId,
		@Valid @RequestBody ChatMessageCreateRequest request
	) {
		ChatMessageResponse response = chatMessageService.createUserMessage(currentUser, projectId, sessionId, request);
		return ApiResponse.onSuccess(SuccessCode.CREATED, response);
	}

	@Operation(summary = "채팅 메시지 목록 조회", description = "채팅 세션의 메시지를 messageOrder 오름차순으로 조회합니다.")
	@GetMapping
	public ResponseEntity<ApiResponse<List<ChatMessageResponse>>> getMessages(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long sessionId
	) {
		List<ChatMessageResponse> responses = chatMessageService.getMessages(currentUser, projectId, sessionId);
		return ApiResponse.onSuccess(SuccessCode.OK, responses);
	}
}
