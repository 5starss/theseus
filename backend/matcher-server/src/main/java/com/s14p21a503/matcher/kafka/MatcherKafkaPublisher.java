package com.s14p21a503.matcher.kafka;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import com.s14p21a503.matcher.dto.ExecutionResult;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Service;

import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;

@Slf4j
public class MatcherKafkaPublisher {

    private final String ticker;
    private final KafkaTemplate<String, Object> kafkaTemplate;
    private final ObjectMapper objectMapper;
    
    private final int queueSize;
    private final long initialBackoffMs;

    // 발행 상태 추적용 (Flush 확인용)
    private final AtomicLong lastEnqueuedId = new AtomicLong(0);
    private final AtomicLong lastPublishedId = new AtomicLong(0);

    // Bounded 큐 (Backpressure 제공)
    private final BlockingQueue<ExecutionResult> queue;
    private final Thread workerThread;
    private volatile boolean running = true;

    public MatcherKafkaPublisher(String ticker, 
                                 KafkaTemplate<String, Object> kafkaTemplate, 
                                 ObjectMapper objectMapper,
                                 int queueSize,
                                 long initialBackoffMs) {
        this.ticker = ticker;
        this.kafkaTemplate = kafkaTemplate;
        this.objectMapper = objectMapper;
        this.queueSize = queueSize;
        this.initialBackoffMs = initialBackoffMs;
        this.queue = new ArrayBlockingQueue<>(queueSize);
        
        this.workerThread = new Thread(this::runWorker, "KafkaPublisher-" + ticker);
        this.workerThread.setDaemon(true);
        this.workerThread.start();
        log.info("[{}] Kafka 전용 발행 워커 시작 (큐: {})", ticker, queueSize);
    }

    @PreDestroy
    public void shutdown() {
        running = false;
        if (workerThread != null) {
            workerThread.interrupt();
        }
    }

    /**
     * 체결 결과를 큐에 넣습니다. 큐가 가득 찼다면 공간이 생길 때까지 대기(Blocking)합니다.
     */
    public void publishExecutionResult(ExecutionResult executionResult) {
        try {
            lastEnqueuedId.incrementAndGet(); // 큐에 넣기 전 ID 증가
            queue.put(executionResult);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            log.error("Kafka 전송 큐 삽입 중 인터럽트 발생 - 데이터: {}", executionResult);
        }
    }

    /**
     * 현재 큐에 있는 모든 데이터가 카프카로 전송 완료될 때까지 대기합니다.
     * @param timeoutMs 대기할 최대 시간
     * @return 전송 완료 여부 (true: 완료, false: 타임아웃)
     */
    public boolean flush(long timeoutMs) {
        long limit = lastEnqueuedId.get();
        long startTime = System.currentTimeMillis();

        log.debug("Kafka 전송 Flush 시작 - 목표 ID: {}, 타임아웃: {}ms", limit, timeoutMs);

        while (lastPublishedId.get() < limit) {
            if (System.currentTimeMillis() - startTime > timeoutMs) {
                log.warn("Kafka 전송 Flush 타임아웃 발생! (현재: {}, 목표: {})", lastPublishedId.get(), limit);
                return false;
            }
            try {
                TimeUnit.MILLISECONDS.sleep(10); // 10ms 단위로 체크
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return false;
            }
        }
        log.debug("Kafka 전송 Flush 완료 - 모든 데이터({}) 송출됨", limit);
        return true;
    }

    private void runWorker() {
        while (running && !Thread.currentThread().isInterrupted()) {
            ExecutionResult result = null;
            try {
                result = queue.take();
                log.info("[{}] [OUT_DEQUEUE] 결과 발행 워커가 이벤트를 꺼냄 - executionId: {}", ticker, result.getExecutionId());
                sendWithRetry(result);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                break;
            } catch (Exception e) {
                log.error("Kafka 워커 루프 중 예외 발생 - 데이터: {}, 예외: {}", result, e.getMessage(), e);
            }
        }
    }

    private void sendWithRetry(ExecutionResult result) {
        String message;
        try {
            message = objectMapper.writeValueAsString(result);
        } catch (JsonProcessingException e) {
            log.error("체결 결과 직렬화 실패 - 스킵함. 데이터: {}", result);
            return;
        }

        long backoffMs = initialBackoffMs; // 설정된 백오프부터 시작
        final long MAX_BACKOFF = 30000; // 최대 30초

        while (running) {
            try {
                // 동기적으로 전송 확인 (.get()을 통해 ACK 대기)
                kafkaTemplate.send(KafkaTopicConstants.EXECUTION_EVENT_TOPIC, result.getTicker(), message)
                        .get(10, TimeUnit.SECONDS);
                
                lastPublishedId.incrementAndGet(); // 발행 성공 시 ID 증가
                log.info("Kafka 체결 결과 전송 성공 - executionId: {}", result.getExecutionId());
                return; // 성공 시 탈출
            } catch (Exception e) {
                log.warn("Kafka 전송 실패 - {}ms 후 재시도 예정. 데이터: {}, 에러: {}", 
                        backoffMs, result.getExecutionId(), e.getMessage());
                
                try {
                    TimeUnit.MILLISECONDS.sleep(backoffMs);
                } catch (InterruptedException ie) {
                    Thread.currentThread().interrupt();
                    return;
                }
                
                // Exponential Backoff (지수적으로 증가)
                backoffMs = Math.min(backoffMs * 2, MAX_BACKOFF);
            }
        }
    }
}
