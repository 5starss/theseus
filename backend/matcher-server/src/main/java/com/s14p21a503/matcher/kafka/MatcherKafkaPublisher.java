package com.s14p21a503.matcher.kafka;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.s14p21a503.matcher.dto.ExecutionResult;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

@Slf4j
@Service
@RequiredArgsConstructor
public class MatcherKafkaPublisher {

    private final KafkaTemplate<String, Object> kafkaTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper().registerModule(new JavaTimeModule());

    /**
     * 체결 결과 전송 메서드
     * 매칭 엔진(PendingOrderManager 등)에서 매수/매도 주문이 매칭되거나
     * 시세 조건에 의해 체결이 일어났을 때 생성된 체결 결과(ExecutionResult)를
     * 코어 API 서버 등 외부 시스템으로 전달하기 위해 카프카에 전송(Publish)합니다.
     * 코어 서버는 이 이벤트를 구독하여 계좌 잔고를 최종적으로 업데이트합니다.
     *
     * @param executionResult 체결된 거래의 상세 정보 (체결가, 수량, 종목코드 등)
     */
    public void publishExecutionResult(ExecutionResult executionResult) {
        try {
            String message = objectMapper.writeValueAsString(executionResult);
            kafkaTemplate.send(KafkaTopicConstants.EXECUTION_EVENT_TOPIC, executionResult.getTicker(), message);
            log.info("Kafka 체결 결과 전송 완료 - 토픽: [{}], 데이터: {}", KafkaTopicConstants.EXECUTION_EVENT_TOPIC, executionResult);
        } catch (JsonProcessingException e) {
            log.error("체결 결과 직렬화 실패 - 데이터: {}, 예외: {}", executionResult, e.getMessage(), e);
        } catch (Exception e) {
            log.error("Kafka 체결 결과 전송 실패 - 데이터: {}, 예외: {}", executionResult, e.getMessage(), e);
        }
    }
}
