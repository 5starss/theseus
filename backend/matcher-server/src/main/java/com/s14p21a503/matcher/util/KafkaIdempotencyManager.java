package com.s14p21a503.matcher.util;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 카프카 메시지 중복 방지를 위한 오프셋 관리 매니저.
 * 복구 시 저널에서 읽어온 마지막 오프셋을 기반으로 실시간 수신 데이터의 중복 여부를 판별합니다.
 */
@Slf4j
@Component
public class KafkaIdempotencyManager {

    // Key: Ticker:Partition, Value: Last Processed Offset
    private final Map<String, Long> lastProcessedOffsets = new ConcurrentHashMap<>();

    /**
     * 특정 토픽/종목/파티션의 처리된 마지막 오프셋을 업데이트합니다.
     */
    public void updateLastOffset(String topic, String ticker, int partition, long offset) {
        if (offset < 0) return;
        String key = makeKey(topic, ticker, partition);
        lastProcessedOffsets.compute(key, (k, old) -> (old == null || offset > old) ? offset : old);
    }

    /**
     * 현재 수신된 메시지가 이미 처리된(저널에 기록된) 메시지인지 확인합니다.
     * 
     * @return true 만약 이미 처리된 오프셋인 경우 (중복)
     */
    public boolean isDuplicate(String topic, String ticker, int partition, long offset) {
        String key = makeKey(topic, ticker, partition);
        Long lastOffset = lastProcessedOffsets.get(key);
        
        if (lastOffset != null && offset <= lastOffset) {
            log.trace("[{}] {} 중복 메시지 감지 (Partition: {}, Offset: {}, Last: {})", 
                    topic, ticker, partition, offset, lastOffset);
            return true;
        }
        return false;
    }

    private String makeKey(String topic, String ticker, int partition) {
        return topic + ":" + ticker + ":" + partition;
    }
    
    public void clear() {
        lastProcessedOffsets.clear();
    }
}
