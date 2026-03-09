package com.s14p21a503.matcher.kafka;

import com.s14p21a503.matcher.dto.*;
import com.s14p21a503.matcher.journal.*;
import com.s14p21a503.matcher.engine.MessageQueueManager;
import com.s14p21a503.matcher.engine.PendingOrderManagerHolder;
import com.s14p21a503.matcher.engine.MatcherConsumer;
import com.s14p21a503.matcher.engine.MarketStateManager;
import com.s14p21a503.matcher.util.OrderIdDeduplicator;
import com.s14p21a503.matcher.util.KafkaIdempotencyManager;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.kafka.support.KafkaHeaders;
import org.springframework.messaging.handler.annotation.Header;
import org.springframework.stereotype.Service;

import java.util.concurrent.ExecutorService;

@Slf4j
@Service
@RequiredArgsConstructor
public class MatcherKafkaListener {

    private final MessageQueueManager queueManager;
    private final PendingOrderManagerHolder orderManagerHolder;
    private final MatcherConsumer matcherConsumer;
    private final OrderIdDeduplicator deduplicator;
    private final KafkaIdempotencyManager idempotencyManager;
    private final JournalService journalService;
    private final MarketStateManager marketStateManager;

    /**
     * 시장 상태 및 이벤트 타임스탬프를 기준으로 이벤트를 무시해야 하는지 판단합니다.
     */
    private boolean shouldIgnoreEvent(String type, String ticker, long timestamp) {
        boolean isMarketOpen = marketStateManager.isMarketOpen();
        boolean isValidTime = marketStateManager.isTimeInMarketHours(timestamp);

        if (!isMarketOpen || !isValidTime) {
            log.warn("[{}] 장외 데이터 무시 처리 - Ticker: {}, MarketOpen: {}, ValidTime: {}", 
                    type, ticker, isMarketOpen, isValidTime);
            return true;
        }
        return false;
    }

    /**
     * 신규 주문 및 주문 취소 요청 수신 리스너.
     * 코어 서버로부터 유입된 주문 이펜트를 중복 체크 후, 
     * 고정밀 복구를 위한 WAL(CMD)을 기록하고 엔진 내부 큐에 적재합니다.
     * 디스크 물리 기록(Flush)이 완료된 후에만 Kafka 오프셋을 커밋합니다.
     *
     * @param orderRequest 주문 요청 데이터
     * @param ack Kafka 수동 승인 객체
     */
    @KafkaListener(topics = KafkaTopicConstants.ORDER_EVENT_TOPIC, groupId = "matcher-group", concurrency = "3")
    public void consumeOrderRequest(OrderRequest orderRequest, 
                                    @Header(KafkaHeaders.OFFSET) long offset,
                                    @Header(KafkaHeaders.RECEIVED_PARTITION) int partition,
                                    Acknowledgment ack) {
        
        // 0. Exactly-Once 체크 (저널 복구와의 중복 방지)
        if (idempotencyManager.isDuplicate(orderRequest.getTicker(), partition, offset)) {
            ack.acknowledge();
            return;
        }

        // 시장 상태 및 타임스탬프 필터링 (모든 Action에 대해 적용)
        if (shouldIgnoreEvent("ORDER", orderRequest.getTicker(), orderRequest.getTimestamp())) {
            idempotencyManager.updateLastOffset(orderRequest.getTicker(), partition, offset);
            ack.acknowledge();
            return;
        }

        log.info("주문 요청 수신: {} (Partition: {}, Offset: {})", orderRequest, partition, offset);
        
        try {
            String ticker = orderRequest.getTicker();
            ExecutorService tickerExecutor = journalService.getExecutor(ticker);

            // 1. 중복 체크 (액션별 독립 체크)
            if (deduplicator.checkAndMarkDuplicate(orderRequest.getOrderId(), orderRequest.getAction())) {
                log.warn("중복 {} 요청 감지 - 무시 처리: {}", orderRequest.getAction(), orderRequest.getOrderId());
                idempotencyManager.updateLastOffset(ticker, partition, offset);
                ack.acknowledge();
                return;
            }

            // 2. WAL (CMD) 기록 요청
            UnifiedJournaler.JournalOutcome outcome = journalService.getJournaler(ticker)
                    .write(JournalType.CMD, 0, partition, offset, JournalSerializer.serialize(orderRequest));
            
            // [최적화] 시퀀스 번호만 나오면 바로 엔진 루프에 넣음 (전용 Executor에서 순서 보장)
            outcome.whenAssigned().thenAcceptAsync(seqNo -> {
                queueManager.enqueue(ticker, seqNo, orderRequest);
                matcherConsumer.ensureConsumerStarted(ticker);
                log.debug("엔진 파이프라인 시작 - Seq: {}", seqNo);
            }, tickerExecutor);

            // [안전성] 디스크 기록(Flush)까지 완료되어야 카프카에게 오프셋 커밋(Ack)
            outcome.whenFlushed().thenAcceptAsync(seqNo -> {
                idempotencyManager.updateLastOffset(ticker, partition, offset);
                ack.acknowledge();
                log.debug("디스크 입고 완료 및 Kafka Ack - Seq: {}", seqNo);
            }, tickerExecutor)
            .exceptionally(e -> {
                log.error("주문 WAL 기록 중 심각한 오류 - Kafka Ack 보류됨: {}", orderRequest.getOrderId(), e);
                return null;
            });
            
        } catch (Exception e) {
            log.error("주문 수신 처리 실패 - OrderId: {}", orderRequest.getOrderId(), e);
        }
    }

    /**
     * [TODO] : 시세서버 구현 후 수정
     * 시세 데이터(호가창) 수신 리스너
     */
    @KafkaListener(topics = KafkaTopicConstants.MARKET_DATA_EVENT_TOPIC, groupId = "matcher-group", concurrency = "3")
    public void consumeMarketData(MarketDataEvent event, 
                                  @Header(KafkaHeaders.OFFSET) long offset,
                                  @Header(KafkaHeaders.RECEIVED_PARTITION) int partition,
                                  @Header(KafkaHeaders.RECEIVED_TIMESTAMP) long timestamp,
                                  Acknowledgment ack) {
        
        // 0. 타임스탬프 주입 (메시지 페이로드에 없는 경우 대비)
        event.setTimestamp(timestamp);
        if (event.getData() == null) {
            log.warn("유효하지 않은 시세 데이터 수신 (data 객체 누락): {}", event);
            ack.acknowledge();
            return;
        }
        String ticker = event.getData().getTicker();

        if (idempotencyManager.isDuplicate(ticker, partition, offset)) {
            ack.acknowledge();
            return;
        }

        // 시장 상태 필터링 (주입된 타임스탬프 사용)
        if (shouldIgnoreEvent("MARKET_DATA", ticker, timestamp)) {
            idempotencyManager.updateLastOffset(ticker, partition, offset);
            ack.acknowledge();
            return;
        }

        log.debug("Kafka 시세 데이터 수신: {} (Partition: {}, Offset: {})", event, partition, offset);

        try {
            ExecutorService tickerExecutor = journalService.getExecutor(ticker);

            UnifiedJournaler.JournalOutcome outcome = journalService.getJournaler(ticker)
                    .write(JournalType.CMD, 0, partition, offset, JournalSerializer.serialize(event));

            outcome.whenAssigned().thenAcceptAsync(seqNo -> {
                queueManager.enqueue(ticker, seqNo, event);
                matcherConsumer.ensureConsumerStarted(ticker);
            }, tickerExecutor);

            outcome.whenFlushed().thenAcceptAsync(seqNo -> {
                idempotencyManager.updateLastOffset(ticker, partition, offset);
                ack.acknowledge();
            }, tickerExecutor);
        } catch (Exception e) {
            log.error("시세 수신 처리 실패 - Ticker: {}", ticker, e);
        }
    }

    /**
     * [TODO] : 시세서버 구현 후 수정
     * 실제 시장 체결(Tick) 데이터 수신 리스너
     */
    @KafkaListener(topics = KafkaTopicConstants.TRADE_DATA_EVENT_TOPIC, groupId = "matcher-group", concurrency = "3")
    public void consumeTradeData(TickDataEvent tickDataEvent, 
                                 @Header(KafkaHeaders.OFFSET) long offset,
                                 @Header(KafkaHeaders.RECEIVED_PARTITION) int partition,
                                 @Header(KafkaHeaders.RECEIVED_TIMESTAMP) long timestamp,
                                 Acknowledgment ack) {
        
        // 0. 타임스탬프 주입
        tickDataEvent.setTimestamp(timestamp);
        String ticker = tickDataEvent.getTicker();

        if (idempotencyManager.isDuplicate(ticker, partition, offset)) {
            ack.acknowledge();
            return;
        }

        // 시장 상태 필터링
        if (shouldIgnoreEvent("TICK", ticker, timestamp)) {
            idempotencyManager.updateLastOffset(ticker, partition, offset);
            ack.acknowledge();
            return;
        }

        log.debug("카프카 체결 데이터(Tick) 수신: {} (Partition: {}, Offset: {})", tickDataEvent, partition, offset);

        try {
            ExecutorService tickerExecutor = journalService.getExecutor(ticker);

            UnifiedJournaler.JournalOutcome outcome = journalService.getJournaler(ticker)
                    .write(JournalType.CMD, 0, partition, offset, JournalSerializer.serialize(tickDataEvent));

            outcome.whenAssigned().thenAcceptAsync(seqNo -> {
                queueManager.enqueue(ticker, seqNo, tickDataEvent);
                matcherConsumer.ensureConsumerStarted(ticker);
            }, tickerExecutor);

            outcome.whenFlushed().thenAcceptAsync(seqNo -> {
                idempotencyManager.updateLastOffset(ticker, partition, offset);
                ack.acknowledge();
            }, tickerExecutor);
        } catch (Exception e) {
            log.error("틱 수신 처리 실패 - Ticker: {}", tickDataEvent.getTicker(), e);
        }
    }

    /**
     * 전역 시장 제어 이벤트 수신 리스너 (Core Server -> Matcher)
     * 장 개시, 종료, 강제 종료 등을 수신하여 엔진 상태를 전역적으로 제어합니다.
     */
    @KafkaListener(topics = KafkaTopicConstants.MARKET_CONTROL_EVENT_TOPIC, groupId = "matcher-control-group")
    public void consumeControlEvent(MarketControlEvent event, Acknowledgment ack) {
        log.info("시장 제어 이벤트 수신: {}", event);
        
        try {
            if (event.getTicker() == null) {
                // 전 종목 제어: PendingOrderManagerHolder를 통해 관리되는 모든 종목에 신호를 보냄
                for (String ticker : orderManagerHolder.getTickers()) {
                    queueManager.enqueue(ticker, -1, event); // 제어 이벤트는 특수 시퀀스(-1) 사용
                    matcherConsumer.ensureConsumerStarted(ticker);
                }
            } else {
                // 특정 종목 제어
                queueManager.enqueue(event.getTicker(), -1, event);
                matcherConsumer.ensureConsumerStarted(event.getTicker());
            }
            ack.acknowledge();
        } catch (Exception e) {
            log.error("시장 제어 이벤트 처리 실패", e);
        }
    }
}
