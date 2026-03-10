package com.s14p21a503.matcher.journal;

import com.s14p21a503.matcher.dto.OrderRequest;
import lombok.Builder;
import lombok.Value;

import java.math.BigDecimal;
import java.util.BitSet;
import java.util.Map;
import java.util.Queue;
import java.util.TreeMap;

/**
 * 매칭 엔진 상태 스냅샷 데이터.
 * 오더북 상태와 중복 방지 필터 상태를 결합하여 저장합니다.
 */
@Value
@Builder
public class SnapshotState implements java.io.Serializable {
    private static final long serialVersionUID = 1L;

    /**
     * 스냅샷이 생성된 시점의 마지막 저널 시퀀스 번호.
     * 복구 시 이 번호 이후의 저널만 재플레이합니다.
     */
    long lastSeqNo;
    
    /**
     * 오더북의 매수 대기열 상태. (가격별 주문 큐)
     */
    TreeMap<BigDecimal, Queue<OrderRequest>> pendingBids;

    /**
     * 오더북의 매도 대기열 상태. (가격별 주문 큐)
     */
    TreeMap<BigDecimal, Queue<OrderRequest>> pendingAsks;

    /**
     * 빠른 주문 조회를 위한 ID 기반 캐시 메모리.
     */
    Map<Long, OrderRequest> orderCache;

    /**
     * 스냅샷 시점의 최우선 매수 호가.
     */
    BigDecimal currentBestBid;

    /**
     * 스냅샷 시점의 최우선 매도 호가.
     */
    BigDecimal currentBestAsk;
    
    /**
     * 주문 중복 방지를 위한 BitSet 버킷들의 상태.
     * 액션(CREATE/CANCEL)별, 버킷 인덱스별로 관리됩니다.
     */
    Map<String, Map<Long, BitSet>> deduplicatorActionBuckets;

    /**
     * 유동성 소수점 적립금 상태.
     */
    @Builder.Default
    BigDecimal liquidityRemainder = BigDecimal.ZERO;
}
