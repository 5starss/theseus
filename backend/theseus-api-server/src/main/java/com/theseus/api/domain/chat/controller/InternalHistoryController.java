package com.theseus.api.domain.chat.controller;

import com.theseus.api.common.response.ApiResponse;
import com.theseus.api.common.response.status.SuccessCode;
import com.theseus.api.domain.chat.dto.request.InternalHistoryMessageCreateRequest;
import com.theseus.api.domain.chat.dto.response.ChatMessageResponse;
import com.theseus.api.domain.chat.service.ChatMessageService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequiredArgsConstructor
@RequestMapping("/api/internal/history/messages")
public class InternalHistoryController {

	private final ChatMessageService chatMessageService;

	@PostMapping
	public ResponseEntity<ApiResponse<ChatMessageResponse>> createMessage(
		@Valid @RequestBody InternalHistoryMessageCreateRequest request
	) {
		ChatMessageResponse response = chatMessageService.createInternalMessage(
			request.getUserId(),
			request.getProjectId(),
			request.getChatSessionId(),
			request.getToolId(),
			request.getSenderType(),
			request.getMessageType(),
			request.getContentType(),
			request.getContent()
		);
		return ApiResponse.onSuccess(SuccessCode.CREATED, response);
	}
}
