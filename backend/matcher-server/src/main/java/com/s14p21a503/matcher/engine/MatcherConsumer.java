package com.s14p21a503.matcher.engine;

import com.s14p21a503.matcher.dto.OrderRequest;
import com.s14p21a503.matcher.dto.OrderType;
import com.s14p21a503.matcher.dto.ExecutionResult;
import com.s14p21a503.matcher.kafka.MatcherKafkaPublisher;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.concurrent.ConcurrentHashMap;

@Slf4j
@Component
@RequiredArgsConstructor
public class MatcherConsumer {

    private final MessageQueueManager queueManager;
    private final PendingOrderManagerHolder orderManagerHolder;
    private final MatcherKafkaPublisher kafkaPublisher;

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

    private void consumeOrders(String ticker) {
        while (!Thread.currentThread().isInterrupted()) {
            try {
                // 해당 종목의 전용 큐에서 블로킹 대기하며 주문을 꺼냄
                OrderRequest order = queueManager.takeOrder(ticker);
                PendingOrderManager orderManager = orderManagerHolder.getManager(ticker);
                
                if ("CANCEL".equalsIgnoreCase(order.getAction())) {
                    ExecutionResult cancelResult = orderManager.cancelOrder(order.getOrderId());
                    if (cancelResult != null) {
                        log.info("주문 처리 취소 완료 - orderId: {}", order.getOrderId());
                        kafkaPublisher.publishExecutionResult(cancelResult);
                    } else {
                        log.warn("취소할 주문을 찾지 못함 (이미 체결되었거나 존재하지 않음) - orderId: {}", order.getOrderId());
                    }
                } else {
                    // 기본 동작 (CREATE) - action이 null이거나 "CREATE"인 경우
                    List<ExecutionResult> results = orderManager.addOrder(order);
                    
                    if (!results.isEmpty()) {
                        log.info("주문 체결 발생 - 종목: {}, 체결수: {}", ticker, results.size());
                        // 체결 결과 전송
                        results.forEach(kafkaPublisher::publishExecutionResult);
                    }
                }
                
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                log.warn("컨슈머 스레드 인터럽트 발생 - 종목: {}", ticker);
            } catch (Exception e) {
                log.error("주문 처리 중 오류 발생 - 종목: {}", ticker, e);
            }
        }
    }
}
