package com.s14p21a503.matcher.kafka;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.datatype.jsr310.JavaTimeModule;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 종목별 MatcherKafkaPublisher 인스턴스를 관리하는 홀더 클래스.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class MatcherKafkaPublisherHolder {

    private final KafkaTemplate<String, Object> kafkaTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper().registerModule(new JavaTimeModule());
    private final Map<String, MatcherKafkaPublisher> publisherMap = new ConcurrentHashMap<>();

    @Value("${matcher.kafka.publish-queue-size:10000}")
    private int queueSize;

    @Value("${matcher.kafka.initial-backoff-ms:1000}")
    private long initialBackoffMs;

    /**
     * 특정 종목의 Publisher 인스턴스를 가져오거나, 없으면 생성합니다.
     */
    public MatcherKafkaPublisher getPublisher(String ticker) {
        return publisherMap.computeIfAbsent(ticker, t -> 
            new MatcherKafkaPublisher(t, kafkaTemplate, objectMapper, queueSize, initialBackoffMs)
        );
    }
}
