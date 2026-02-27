package com.s14p21a503.coreapi.common.kafka;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Service;

import java.util.concurrent.CompletableFuture;

@Service
public class KafkaProducerService {

    private static final Logger log = LoggerFactory.getLogger(KafkaProducerService.class);
    
    private final KafkaTemplate<String, Object> kafkaTemplate;

    public KafkaProducerService(KafkaTemplate<String, Object> kafkaTemplate) {
        this.kafkaTemplate = kafkaTemplate;
    }

    /**
     * 카프카 메시지 비동기 발행 (공통)
     *
     * @param topic 발행할 카프카 토픽
     * @param data  발행할 데이터 객체 (JsonSerializer에 의해 JSON 변환됨)
     */
    public void sendMessage(String topic, Object data) {
        log.info("Kafka 메시지 전송 시작 - 토픽: {}, 데이터: {}", topic, data);

        CompletableFuture<SendResult<String, Object>> future = kafkaTemplate.send(topic, data);

        future.whenComplete((result, ex) -> {
            if (ex == null) {
                log.info("Kafka 메시지 전송 완료 - 토픽: [{}], 파티션: [{}], 오프셋: [{}]",
                        topic,
                        result.getRecordMetadata().partition(),
                        result.getRecordMetadata().offset());
            } else {
                log.error("Kafka 메시지 전송 실패 - 토픽: [{}], 예외: {}", topic, ex.getMessage(), ex);
            }
        });
    }

    /**
     * 카프카 메시지 키를 지정하여 발행
     * 동일한 로직(예: 동일한 유저, 동일한 주식 종목)에 대해 메시지 순서 보장이 필요할 때 Key를 지정합니다.
     * 같은 Key를 가진 메시지는 동일한 파티션에 들어갑니다.
     *
     * @param topic 발행할 카프카 토픽
     * @param key   메시지 키 (파티션 분배의 기준)
     * @param data  발행할 데이터 객체
     */
    public void sendMessageWithKey(String topic, String key, Object data) {
        log.info("Kafka 메시지 전송 시작 (Key 포함) - 토픽: {}, Key: {}, 데이터: {}", topic, key, data);

        CompletableFuture<SendResult<String, Object>> future = kafkaTemplate.send(topic, key, data);

        future.whenComplete((result, ex) -> {
            if (ex == null) {
                log.info("Kafka 메시지 전송 완료 - 토픽: [{}], Key: [{}], 파티션: [{}], 오프셋: [{}]",
                        topic,
                        key,
                        result.getRecordMetadata().partition(),
                        result.getRecordMetadata().offset());
            } else {
                log.error("Kafka 메시지 전송 실패 - 토픽: [{}], Key: [{}], 예외: {}", topic, key, ex.getMessage(), ex);
            }
        });
    }
}
