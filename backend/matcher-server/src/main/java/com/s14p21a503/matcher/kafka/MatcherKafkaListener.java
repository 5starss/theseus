package com.s14p21a503.matcher.kafka;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.s14p21a503.matcher.dto.ExecutionResult;
import com.s14p21a503.matcher.dto.MarketDataEvent;
import com.s14p21a503.matcher.dto.OrderRequest;
import com.s14p21a503.matcher.engine.MessageQueueManager;
import com.s14p21a503.matcher.engine.PendingOrderManagerHolder;
import com.s14p21a503.matcher.engine.MatcherConsumer;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Service;

import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class MatcherKafkaListener {

    private final MessageQueueManager queueManager;
    private final PendingOrderManagerHolder orderManagerHolder;
    private final MatcherKafkaPublisher kafkaPublisher;
    private final ObjectMapper objectMapper;
    private final MatcherConsumer matcherConsumer;

    /**
     * 신규 주문 및 취소 요청 수신 리스너 (단일 토픽으로 순서 보장)
     * 코어 API 서버에서 발행한 사용자 주문(CREATE/CANCEL) 이벤트를 구독하여
     * 체결 엔진 내부의 메모리 큐(MessageQueueManager)에 적재합니다.
     * 단일 토픽(order-events)의 파티션을 통해 종목별(Key=Ticker) 이벤트 순서를 완벽히 보장합니다.
     * 적재된 주문은 별도의 컨슈머(MatcherConsumer) 스레드에 의해 순차적으로 처리됩니다.
     * 
     * @param message 카프카에서 수신한 JSON 형태의 주문 데이터 (OrderRequest)
     */
    @KafkaListener(topics = KafkaTopicConstants.ORDER_EVENT_TOPIC, groupId = "matcher-group", concurrency = "3")
    public void consumeOrderRequest(String message) {
        try {
            OrderRequest orderRequest = objectMapper.readValue(message, OrderRequest.class);
            log.info("Kafka 주문/취소 요청 수신 - 데이터: {}", orderRequest);
            
            // 1. 해당 종목의 전담 컨슈머 스레드가 없다면 생성/시작 (Thread per Ticker)
            matcherConsumer.ensureConsumerStarted(orderRequest.getTicker());
            
            // 2. 큐에 주문/취소 적재 (내부 메모리 종목별 큐로 전달, 순서 보장)
            queueManager.enqueue(orderRequest);
            
        } catch (Exception e) {
            log.error("주문/취소 요청 메시지 처리 실패 - 데이터: {}, 예외: {}", message, e.getMessage(), e);
        }
    }

    /**
     * 시세 데이터(호가창) 수신 리스너
     * 외부 거래소(예: 한국투자증권 웹소켓) 등에서 들어온 현재 최우선 매수/매도 호가 변경 이벤트를 구독합니다.
     * 변경된 시세를 해당 종목의 대기 주문 관리자(PendingOrderManager)에 즉시 반영하며,
     * 시세 변동으로 인해 체결 조건이 충족된 대기 주문들을 찾아 즉시 체결 및 체결 이벤트를 발행합니다.
     *
     * @param message 카프카에서 수신한 JSON 형태의 시세 데이터 (MarketDataEvent)
     */
    @KafkaListener(topics = KafkaTopicConstants.MARKET_DATA_EVENT_TOPIC, groupId = "matcher-group")
    public void consumeMarketData(String message) {
        try {
            // TODO [외부 시세 연동]: 
            // 현재는 내부 DTO 형식을 기대하고 파싱합니다. 실제 외부 시세 파이프라인이 연결되면,
            // 외부 시스템이 쏘아주는 원본 JSON 문자열을 파싱하기 위해 Custom Deserializer를 사용하거나,
            // 전용 Wrapper DTO를 거쳐서 MarketDataEvent로 변환하는 매핑 로직이 이곳에 추가되어야 합니다.
            MarketDataEvent event = objectMapper.readValue(message, MarketDataEvent.class);
            log.debug("Kafka 시세 데이터(1호가) 수신 - 데이터: {}", event);

            // 해당 종목의 대기 주문 관리자를 가져와서 시세 도달 시 체결 처리
            var orderManager = orderManagerHolder.getManager(event.getTicker());
            List<ExecutionResult> results = orderManager.updateMarketDataAndMatch(event);

            if (!results.isEmpty()) {
                log.info("시세 도달로 인한 매칭 체결 발생 - 결과: {}", results);
                // 체결 결과 전송
                results.forEach(kafkaPublisher::publishExecutionResult);
            }

        } catch (Exception e) {
            log.error("시세 데이터 메시지 처리 실패 - 데이터: {}, 예외: {}", message, e.getMessage(), e);
        }
    }
}
