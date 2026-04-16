package com.s14p21a503.matcher.util;

import org.springframework.stereotype.Component;
import java.util.BitSet;
import java.util.concurrent.ConcurrentHashMap;
import java.util.Map;
import lombok.extern.slf4j.Slf4j;

/**
 * DB의 Auto-increment 특성을 활용한 주문 ID 중복 방지 유틸리티.
 * BitSet을 사용하여 1,000,000건당 약 125KB의 극소량 메모리만 소모합니다.
 */
@Slf4j
@Component
public class OrderIdDeduplicator {
    // 100만 단위의 버킷으로 나누어 메모리 팽창 방지 및 효율적 관리
    private static final int BUCKET_SIZE = 1_000_000;
    // 액션별로 독립적인 버킷 관리 (CREATE, CANCEL)
    private final Map<String, Map<Long, BitSet>> actionBuckets = new ConcurrentHashMap<>();

    /**
     * 주문 ID와 액션의 중복 여부를 체크하고, 처음 수신된 조합이라면 기록합니다.
     * 
     * @param orderId 체크할 주문 ID
     * @param action 주문 액션 (CREATE, CANCEL)
     * @return 중복이면 true, 처음 수신이면 false (기록 완료)
     */
    public boolean checkAndMarkDuplicate(Long orderId, String action) {
        if (orderId == null || orderId < 0 || action == null) {
            return false;
        }
        
        String normalizedAction = action.toUpperCase();
        Map<Long, BitSet> buckets = actionBuckets.computeIfAbsent(normalizedAction, k -> new ConcurrentHashMap<>());

        long bucketIndex = orderId / BUCKET_SIZE;
        int bitIndex = (int) (orderId % BUCKET_SIZE);

        // 버킷이 없다면 생성 (Thread-safe)
        BitSet bucket = buckets.computeIfAbsent(bucketIndex, k -> {
            log.debug("[{}] 새로운 OrderId 중복 방지 버킷 생성 - 인덱스: {}", normalizedAction, k);
            return new BitSet(BUCKET_SIZE);
        });
        
        synchronized (bucket) {
            if (bucket.get(bitIndex)) {
                return true;
            }
            bucket.set(bitIndex);
            return false;
        }
    }

    /**
     * 일일 초기화 또는 시스템 재시작 시 메모리 정리를 위해 사용합니다.
     */
    public void clear() {
        log.info("OrderId 중복 방지 필터 초기화 - 전체 버킷 제거");
        actionBuckets.clear();
    }
    
    /**
     * 현재 상태를 복사하여 반환 (스냅샷 전용).
     */
    public Map<String, Map<Long, BitSet>> getActionBucketsCopy() {
        Map<String, Map<Long, BitSet>> fullCopy = new ConcurrentHashMap<>();
        actionBuckets.forEach((action, buckets) -> {
            Map<Long, BitSet> actionCopy = new ConcurrentHashMap<>();
            buckets.forEach((k, v) -> {
                synchronized (v) {
                    actionCopy.put(k, (BitSet) v.clone());
                }
            });
            fullCopy.put(action, actionCopy);
        });
        return fullCopy;
    }

    /**
     * 외부 상태로 복원 (스냅샷 복구용).
     */
    public void restoreState(Map<String, Map<Long, BitSet>> state) {
        if (state != null) {
            actionBuckets.clear();
            actionBuckets.putAll(state);
            log.info("OrderId 중복 방지 필터 상태 복원 완료");
        }
    }

    public int getBucketCount() {
        return actionBuckets.values().stream().mapToInt(Map::size).sum();
    }
}
