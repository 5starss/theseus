package com.s14p21a503.coreapi.domain.notification.service;

import com.s14p21a503.coreapi.domain.notification.dto.NotificationResponseDto;
import com.s14p21a503.coreapi.domain.notification.event.ExecutionNotificationEvent;
import com.s14p21a503.coreapi.domain.notification.repository.EmitterRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Service;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;

@Slf4j
@Service
@RequiredArgsConstructor
public class NotificationService {

    private final EmitterRepository emitterRepository;

    /**
     * 사용자가 SSE를 통해 알림을 구독합니다.
     */
    public SseEmitter subscribe(Long userId) {
        // 기본 60분 타임아웃 (0은 무제한이지만 연결 관리를 위해 시간을 설정.)
        SseEmitter emitter = new SseEmitter(60 * 60 * 1000L); 
        
        // 연결 완료 시 삭제 로직
        emitter.onCompletion(() -> emitterRepository.deleteById(userId));
        // 타임아웃 시 삭제 로직
        emitter.onTimeout(() -> emitterRepository.deleteById(userId));
        // 에러 시 삭제 로직
        emitter.onError((e) -> emitterRepository.deleteById(userId));

        // 503 에러 방지를 위해 첫 연결 시 더미 데이터 전송
        try {
            emitter.send(SseEmitter.event()
                    .name("connect")
                    .data("Connected to Real-time Notification Server"));
        } catch (IOException e) {
            log.error("SSE 초기 연결 실패 - userId: {}", userId, e);
            emitter.completeWithError(e);
            return emitter;
        }

        emitterRepository.save(userId, emitter);
        return emitter;
    }

    /**
     * 트랜잭션 커밋 완료 후 실시간 알림을 전송합니다. (SSE 전송)
     */
    @Async("notificationExecutor")
    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void sendNotification(ExecutionNotificationEvent event) {
        SseEmitter emitter = emitterRepository.get(event.userId());
        if (emitter == null) return;

        log.info("SSE 알림 전송 - userId: {}, payload: {}", event.userId(), event.payload());
        
        var dto = event.payload();
        NotificationResponseDto response = new NotificationResponseDto(
                dto.getEventType(),
                dto.getOrderType(),
                dto.getTicker(),
                event.stockName(),
                dto.getMatchPrice(),
                dto.getMatchQuantity(),
                dto.getExecutedAt()
        );

        try {
            emitter.send(SseEmitter.event()
                    .name("order_notification") // 이벤트 이름
                    .data(response)); // 실제 데이터
        } catch (IOException e) {
            log.error("SSE 전송 실패 - userId: {}", event.userId(), e);
            emitterRepository.deleteById(event.userId());
        }
    }
}
