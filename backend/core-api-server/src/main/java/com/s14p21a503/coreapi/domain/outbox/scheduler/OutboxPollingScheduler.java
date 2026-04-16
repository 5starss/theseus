package com.s14p21a503.coreapi.domain.outbox.scheduler;

import com.s14p21a503.coreapi.common.kafka.KafkaProducerService;
import com.s14p21a503.coreapi.domain.outbox.entity.OutboxEvent;
import com.s14p21a503.coreapi.domain.outbox.entity.OutboxStatus;
import com.s14p21a503.coreapi.domain.outbox.repository.OutboxEventRepository;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

@Slf4j
@Component
public class OutboxPollingScheduler {

    private final OutboxEventRepository outboxEventRepository;
    private final KafkaProducerService kafkaProducerService;
    private final com.fasterxml.jackson.databind.ObjectMapper objectMapper;

    public OutboxPollingScheduler(OutboxEventRepository outboxEventRepository, 
                                  KafkaProducerService kafkaProducerService,
                                  com.fasterxml.jackson.databind.ObjectMapper objectMapper) {
        this.outboxEventRepository = outboxEventRepository;
        this.kafkaProducerService = kafkaProducerService;
        this.objectMapper = objectMapper;
    }

    /**
     * 1초마다 실행되어 아직 카프카 전송이 되지 않은(INIT) 이벤트들을 순차적으로 뽑아 발송합니다.
     */
    @Scheduled(fixedDelay = 1000)
    @Transactional
    public void processOutboxEvents() {
        // 1. INIT 상태의 이벤트를 가장 오래된 순으로 가져옴 (1회 배치당 최대 50건 처리)
        List<OutboxEvent> events = outboxEventRepository.findTop50ByStatusOrderByCreatedAtAsc(OutboxStatus.INIT);
        
        if (events.isEmpty()) {
            return;
        }

        log.debug("아웃박스 폴링 스케줄러 실행: {}건의 미발송 이벤트 발견 및 발송 시작", events.size());

        for (OutboxEvent event : events) {
            try {
                // 이중 직렬화 방지
                Object payloadObj = objectMapper.readValue(event.getPayload(), Object.class);

                // 2. 카프카 발송
                kafkaProducerService.sendMessageWithKey(event.getTopic(), event.getMessageKey(), payloadObj);
                
                // 3. 상태 업데이트 (성공)
                event.markAsPublished();
            } catch (Exception e) {
                log.error("아웃박스 카프카 이벤트 전송 실패 [Event ID: {}]: {}", event.getId(), e.getMessage());
            }
        }
    }

    /**
     * 매일 새벽 4시에 7일이 지난 전송 완료(PUBLISHED) 아웃박스 이벤트를 일괄 삭제합니다.
     * 이를 통해 테이블 팽창을 막고 성능을 최적화합니다.
     */
    @Scheduled(cron = "0 0 4 * * *")
    @Transactional
    public void cleanupOldOutboxEvents() {
        LocalDateTime cutoffDate = LocalDateTime.now().minusDays(7);
        int deletedCount = outboxEventRepository.deleteOldEvents(OutboxStatus.PUBLISHED, cutoffDate);
        log.info("오래된 아웃박스 이벤트 정리 스케줄러 실행: {}건 삭제 완료 (기준일: {})", deletedCount, cutoffDate);
    }
}
