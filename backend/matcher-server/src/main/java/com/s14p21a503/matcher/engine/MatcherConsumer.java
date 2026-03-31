package com.s14p21a503.matcher.engine;

import com.s14p21a503.matcher.dto.*;
import com.s14p21a503.matcher.kafka.MatcherKafkaPublisher;
import com.s14p21a503.matcher.kafka.MatcherKafkaPublisherHolder;
import com.s14p21a503.matcher.journal.*;
import com.s14p21a503.matcher.util.OrderIdDeduplicator;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.io.IOException;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Slf4j
@Component
@RequiredArgsConstructor
public class MatcherConsumer {

    private final MessageQueueManager queueManager;
    private final PendingOrderManagerHolder orderManagerHolder;
    private final MatcherKafkaPublisherHolder publisherHolder;
    private final MarketStateManager marketStateManager;
    private final HolidayManager holidayManager;

    private final ConcurrentHashMap<String, Thread> consumerThreads = new ConcurrentHashMap<>();

    /**
     * 특정 종목(ticker)에 대한 전담 컨슈머 스레드가 없다면 생성하고 실행합니다.
     */
    public void ensureConsumerStarted(String ticker) {
        consumerThreads.computeIfAbsent(ticker, key -> {
            Thread thread = new Thread(() -> consumeOrders(key), "Consumer-" + key);
            thread.setDaemon(true);
            thread.start();
            log.info("체결 엔진 컨슈머 스레드 생성 및 시작 완료 - 종목: {}", key);
            return thread;
        });
    }

    /**
     * 해당 종목의 전용 메시지 큐(MessageQueueManager)에서 이벤트를 무한 루프로 꺼내어 처리합니다.
     * 단일 종목에 대해 하나의 전담 스레드만 이 루프를 수행하므로,
     * 주문 요청과 체결 데이터의 선후 관계가 큐에 적재된 순서대로 엄격히 보장되어 데이터 정합성을 유지합니다.
     * 
     * 처리 흐름:
     * 1. OrderRequest (CANCEL): 대기열에서 해당 주문을 즉시 제거하고 취소 결과를 발행합니다.
     * 2. OrderRequest (CREATE): 신규 주문을 호가창 대기열에 추가합니다. 실제 체결은 향후 틱 발생 시 수행됩니다.
     * 3. TickDataEvent: 시장 체결 발생 시, 대기 중인 주문들의 가격 조건과 유동성을 체크하여 매칭 및 부분 체결을 수행합니다.
     *
     * @param ticker 처리 대상 종목 코드 (Ticker)
     */
    private final OrderIdDeduplicator orderIdDeduplicator;
    private final JournalService journalService;
    private final SnapshotService snapshotService;

    // 종목별 처리된 이벤트 카운트 (스냅샷 주기 관리용)
    private final Map<String, Long> processedCountMap = new ConcurrentHashMap<>();
    private static final long SNAPSHOT_INTERVAL = 5000; // 5,000건마다 스냅샷 (성능과 복구 시간의 균형)

    private void consumeOrders(String ticker) {
        // [무한 루프] 종목별 전담 스레드가 큐를 계속 감시하며 이벤트를 처리합니다.
        while (!Thread.currentThread().isInterrupted()) {
            try {
                // 1. [Event Pop] 통합 큐(MessageQueueManager)에서 시퀀싱된 이벤트를 순차적으로 꺼냅니다.
                JournaledEvent journaledEvent = queueManager.takeOrder(ticker);
                Object event = journaledEvent.getEvent();
                long cmdSeqNo = journaledEvent.getSeqNo();
                int partition = journaledEvent.getPartition();
                long offset = journaledEvent.getOffset();
                long startTime = System.currentTimeMillis();
                
                if (event instanceof TickDataEvent || event instanceof MarketDataEvent) {
                    if (log.isDebugEnabled()) {
                        log.debug("[{}] [DEQUEUE] 시세/틱 처리 - Seq: {}", ticker, cmdSeqNo);
                    }
                } else {
                    log.info("[{}] [PROCESS_START] 주문/제어 처리 시작 - Seq: {}, Type: {}", 
                            ticker, cmdSeqNo, event.getClass().getSimpleName());
                }
                
                PendingOrderManager orderManager = orderManagerHolder.getManager(ticker);
                UnifiedJournaler journaler = journalService.getJournaler(ticker);

                // 2. [Event Routing] 이벤트 타입에 따라 적절한 엔진 로직을 수행합니다.
                if (event instanceof OrderRequest) {
                    OrderRequest order = (OrderRequest) event;

                    if ("CANCEL".equalsIgnoreCase(order.getAction())) {
                        // [Case A: 주문 취소] 오더북에서 즉시 제거하고 결과를 저널에 씁니다.
                        ExecutionResult cancelResult = orderManager.cancelOrder(order.getOrderId(), partition, offset);
                        if (cancelResult != null) {
                            processExecutionResult(ticker, journaler, cmdSeqNo, cancelResult);
                        }
                    } else {
                        // [Case B: 주문 생성] 오더북 대기열(TreeMap)에 적재합니다.
                        orderManager.addOrder(order);
                        
                        // [Async] COMMIT 기록 (대기하지 않음)
                        journaler.write(JournalType.COMMIT, cmdSeqNo, null);
                        
                        // 중복 방지 필터에 마킹
                        orderIdDeduplicator.checkAndMarkDuplicate(order.getOrderId(), order.getAction());
                    }
                } else if (event instanceof TickDataEvent) {
                    // [Case C: 시장 체결(Tick)] 가용 유동성을 계산하여 대기 오더와 매칭을 수행합니다.
                    TickDataEvent tick = (TickDataEvent) event;
                    List<ExecutionResult> results = orderManager.matchWithTick(tick, cmdSeqNo, partition, offset);

                    // 각 개별 체결 결과에 대해 저널 기록 및 외부(Kafka) 발행을 수행합니다.
                    for (ExecutionResult res : results) {
                        processExecutionResult(ticker, journaler, cmdSeqNo, res);
                    }
                    
                    // 해당 틱에 의한 모든 매칭 처리가 끝났음을 COMMIT 기록으로 확정 (비차단)
                    journaler.write(JournalType.COMMIT, cmdSeqNo, null);
                } else if (event instanceof MarketDataEvent) {
                    // [Case D: 호가 업데이트] 엔진 내부의 최우선 호가 정보(Best Bid/Ask)를 갱신합니다.
                    MarketDataEvent mkt = (MarketDataEvent) event;
                    orderManager.updateMarketData(mkt);
                    journaler.write(JournalType.COMMIT, cmdSeqNo, null);
                } else if (event instanceof MarketControlEvent) {
                    // [Case E: 관리용 제어 이벤트] 장 개시/종료/강제제어 명령을 처리합니다.
                    MarketControlEvent control = (MarketControlEvent) event;
                    log.info("[{}] 시장 제어 이벤트 처리 시작: {}", ticker, control.getType());

                    switch (control.getType()) {
                        case MARKET_OPEN:
                        case MARKET_RESUME:
                            // 개장 신호와 함께 전달된 휴장일 리스트가 있다면 동기화 수행
                            if (control.getHolidayDates() != null) {
                                holidayManager.updateHolidays(new HashSet<>(control.getHolidayDates()));
                            }
                            marketStateManager.setStatus(MarketStatus.OPEN);
                            break;
                        case MARKET_HALT:
                            marketStateManager.setStatus(MarketStatus.HALT);
                            break;
                        case MARKET_CLOSE:
                            marketStateManager.setStatus(MarketStatus.CLOSE);
                            // 모든 미체결 주문 일괄 취소 (정규 종료 시에만 수행)
                            List<ExecutionResult> results = orderManager.cancelAllOrders();
                            for (ExecutionResult res : results) {
                                processExecutionResult(ticker, journaler, cmdSeqNo, res);
                            }
                            break;
                        case SET_HOLIDAYS:
                            log.info("[{}] 수동 휴장일 업데이트 이벤트 수신: {}건", ticker, 
                                    control.getHolidayDates() != null ? control.getHolidayDates().size() : 0);
                            if (control.getHolidayDates() != null) {
                                holidayManager.updateHolidays(new java.util.HashSet<>(control.getHolidayDates()));
                            }
                            break;
                    }
                    
                    // 제어 이벤트 처리가 완료되었음을 저널에 기록
                    journaler.write(JournalType.COMMIT, cmdSeqNo, null);
                }

                long duration = System.currentTimeMillis() - startTime;
                if (!(event instanceof TickDataEvent || event instanceof MarketDataEvent)) {
                    log.info("[{}] [PROCESS_END] 처리 완료 - Seq: {}, Duration: {}ms", ticker, cmdSeqNo, duration);
                } else if (log.isDebugEnabled()) {
                    log.debug("[{}] [PROCESS_END] 시세/틱 처리 완료 - Seq: {}, Duration: {}ms", ticker, cmdSeqNo, duration);
                }

                // 3. [Snapshot] 주기적으로 덤프를 생성하여 장애 복구 시 리플레이 시간을 단축합니다.
                long currentCount = processedCountMap.getOrDefault(ticker, 0L) + 1;
                processedCountMap.put(ticker, currentCount);

                if (currentCount % SNAPSHOT_INTERVAL == 0) {
                    snapshotService.saveSnapshot(ticker, cmdSeqNo);
                }

            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                log.warn("컨슈머 스레드 인터럽트 발생 - 종목: {}", ticker);
            } catch (Exception e) {
                log.error("주문 처리 중 오류 발생 - 종목: {}", ticker, e);
            }
        }
    }

    private void processExecutionResult(String ticker, UnifiedJournaler journaler, long cmdSeqNo, ExecutionResult res) throws Exception {
        // 1. RES 저널 기록 (비차단 요청)
        UnifiedJournaler.JournalOutcome outcome = journaler.write(JournalType.RES, cmdSeqNo, JournalSerializer.serialize(res));
        
        // 2. 디스크 기록 완료(fsync) 시점에 종목별 전용 스레드에서 비동기 후속 처리
        // 이를 통해 엔진(Consumer) 스레드는 I/O를 기다리지 않고 즉시 다음 작업을 수행할 수 있습니다.
        outcome.whenFlushed().thenAcceptAsync(seq -> {
            try {
                // 카프카 발행 (종목별 전용 Publisher 사용)
                publisherHolder.getPublisher(ticker).publishExecutionResult(res);
                
                // Deduplicator 최종 마킹 (중복 방지)
                String dedupAction = (res.getEventType() == EventType.CANCELLED) ? "CANCEL" : "CREATE";
                orderIdDeduplicator.checkAndMarkDuplicate(res.getOrderId(), dedupAction);
                
                if (log.isTraceEnabled()) {
                    log.trace("[{}] 비동기 발행 완료 (Seq: {})", ticker, seq);
                }
            } catch (Exception e) {
                log.error("[{}] 비동기 발행 중 오류 발생 (Seq: {})", ticker, seq, e);
            }
        }, journalService.getExecutor(ticker));
    }
}
