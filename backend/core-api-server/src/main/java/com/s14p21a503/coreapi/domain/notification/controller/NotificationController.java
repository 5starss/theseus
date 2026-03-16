package com.s14p21a503.coreapi.domain.notification.controller;

import com.s14p21a503.coreapi.domain.notification.service.NotificationService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

@Tag(name = "Notification", description = "실시간 알림 API (SSE)")
@RestController
@RequiredArgsConstructor
@RequestMapping("/api/v1/notifications")
public class NotificationController {

    private final NotificationService notificationService;

    /**
     * 실시간 알림 구독을 위해 SSE 연결을 맺습니다.
     * 프론트엔드 연결: new EventSource('...')
     */
    @Operation(summary = "실시간 알림 구독", description = "SSE 프로토콜을 사용하여 실시간 알림을 구독합니다.")
    @GetMapping(value = "/subscribe", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter subscribe(@RequestHeader(value = "X-User-Id") Long userId) {
        return notificationService.subscribe(userId);
    }
}
