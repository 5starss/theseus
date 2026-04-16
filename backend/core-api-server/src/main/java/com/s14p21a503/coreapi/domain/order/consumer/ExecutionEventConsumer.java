package com.s14p21a503.coreapi.domain.order.consumer;

import com.s14p21a503.coreapi.common.kafka.KafkaTopicConstants;
import com.s14p21a503.coreapi.domain.order.dto.ExecutionEventDto;
import com.s14p21a503.coreapi.domain.order.service.ExecutionLedgerService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.kafka.annotation.DltHandler;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.annotation.RetryableTopic;
import org.springframework.kafka.retrytopic.TopicSuffixingStrategy;
import org.springframework.messaging.handler.annotation.Payload;
import org.springframework.retry.annotation.Backoff;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
public class ExecutionEventConsumer {

    private final ExecutionLedgerService executionLedgerService;

    @RetryableTopic(
            attempts = "3",
            backoff = @Backoff(delay = 1000, multiplier = 2.0),
            topicSuffixingStrategy = TopicSuffixingStrategy.SUFFIX_WITH_INDEX_VALUE,
            dltTopicSuffix = ".dlq"
    )
    @KafkaListener(topics = KafkaTopicConstants.EXECUTION_EVENT_TOPIC, groupId = "core-group")
    public void consume(@Payload ExecutionEventDto event) {
        log.info("체결 이벤트 수신 - executionId: {}, orderId: {}, eventType: {}",
                event.getExecutionId(), event.getOrderId(), event.getEventType());
        try {
            executionLedgerService.processExecution(event);
        } catch (DataIntegrityViolationException e) {
            log.warn("중복 체결 이벤트 감지 (race condition), 무시 - executionId: {}, message: {}",
                    event.getExecutionId(), e.getMessage());
        }
    }

    @DltHandler
    public void consumeDlq(@Payload ExecutionEventDto event) {
        log.error("체결 이벤트 최종 실패 - 주문 취소 처리 - orderId: {}, eventType: {}",
                event.getOrderId(), event.getEventType());
        executionLedgerService.processExecutionFailure(event);
    }
}
