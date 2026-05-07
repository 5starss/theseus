package com.theseus.api.domain.toolgeneration.controller;

import com.theseus.api.domain.auth.token.AuthenticatedUser;
import com.theseus.api.domain.toolgeneration.service.ToolGenerationEventStreamService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@RestController
@RequiredArgsConstructor
@Tag(name = "ToolGeneration", description = "Tool 생성 진행 이벤트 API")
@RequestMapping("/api/v1/projects/{projectId}/sessions/{sessionId}/tools/{toolId}")
public class ToolGenerationEventStreamController {

	private final ToolGenerationEventStreamService toolGenerationEventStreamService;

	@Operation(summary = "Tool 생성 진행 이벤트 구독", description = "Tool 생성 진행 상태를 Server-Sent Events로 구독합니다.")
	@GetMapping(value = "/events", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
	public SseEmitter subscribeToolGenerationEvents(
		@AuthenticationPrincipal AuthenticatedUser currentUser,
		@PathVariable Long projectId,
		@PathVariable Long sessionId,
		@PathVariable Long toolId
	) {
		return toolGenerationEventStreamService.subscribe(currentUser, projectId, sessionId, toolId);
	}
}
