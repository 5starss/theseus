package com.s14p21a503.matcher.engine;

import com.s14p21a503.matcher.dto.MarketDataEvent;
import com.s14p21a503.matcher.dto.OrderRequest;
import com.s14p21a503.matcher.dto.OrderType;
import com.s14p21a503.matcher.dto.ExecutionResult;
import com.s14p21a503.matcher.dto.EventType;
import com.s14p21a503.matcher.dto.OrderType;
import com.s14p21a503.matcher.util.ExecutionIdGenerator;
import lombok.Getter;
import lombok.extern.slf4j.Slf4j;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.locks.ReentrantLock;

@Slf4j
public class PendingOrderManager {

    @Getter
    private final String ticker;

    // 가격 우선(TreeMap) 및 시간 우선(Queue) 보장을 위한 자료구조
    // 매수(Bid): 높은 가격이 우선이므로 내림차순 정렬
    private final TreeMap<BigDecimal, Queue<OrderRequest>> pendingBids = new TreeMap<>(Collections.reverseOrder());
    // 매도(Ask): 낮은 가격이 우선이므로 오름차순 정렬 (기본값)
    private final TreeMap<BigDecimal, Queue<OrderRequest>> pendingAsks = new TreeMap<>();

    // 빠른 주문 취소를 위한 참조용 캐시 (O(1) 탐색용)
    private final Map<Long, OrderRequest> orderCache = new HashMap<>();

    // 현재 시장 1호가 캐싱
    private BigDecimal currentBestBid;
    private BigDecimal currentBestAsk;

    private final ReentrantLock lock = new ReentrantLock();

    public PendingOrderManager(String ticker) {
        this.ticker = ticker;
    }

    /**
     * 주문 추가 (수신 즉시 체결 가능한지 확인 후, 안되면 대기열에 추가)
     */
    public List<ExecutionResult> addOrder(OrderRequest order) {
        lock.lock();
        try {
            List<ExecutionResult> trades = new ArrayList<>();
            if (order.getOrderType() == OrderType.BUY) {
                // 매수 주문: 내 지정가가 시장 매도 1호가(bestAsk)보다 크거나 같으면 즉시 체결
                if (currentBestAsk != null && order.getPrice().compareTo(currentBestAsk) >= 0) {
                    trades.add(createExecutionResult(order, EventType.MATCHED, currentBestAsk));
                } else {
                    pendingBids.computeIfAbsent(order.getPrice(), k -> new LinkedList<>()).add(order);
                    orderCache.put(order.getOrderId(), order);
                }
            } else if (order.getOrderType() == OrderType.SELL) {
                // 매도 주문: 내 지정가가 시장 매수 1호가(bestBid)보다 작거나 같으면 즉시 체결
                if (currentBestBid != null && order.getPrice().compareTo(currentBestBid) <= 0) {
                    trades.add(createExecutionResult(order, EventType.MATCHED, currentBestBid));
                } else {
                    pendingAsks.computeIfAbsent(order.getPrice(), k -> new LinkedList<>()).add(order);
                    orderCache.put(order.getOrderId(), order);
                }
            }
            return trades;
        } finally {
            lock.unlock();
        }
    }

    /**
     * 시세 업데이트 수신 시, 대기 중인 주문들을 훑어서 조건에 맞으면 체결시킴
     */
    public List<ExecutionResult> updateMarketDataAndMatch(MarketDataEvent event) {
        lock.lock();
        try {
            this.currentBestBid = event.getBestBid();
            this.currentBestAsk = event.getBestAsk();
            
            List<ExecutionResult> trades = new ArrayList<>();

            // 1. 대기 매수 주문 검사: 제일 비싸게 부른 사람부터 시장 매도 1호가(bestAsk) 이하로 살 수 있는지 검사
            if (this.currentBestAsk != null) {
                Iterator<Map.Entry<BigDecimal, Queue<OrderRequest>>> bidIterator = pendingBids.entrySet().iterator();
                while (bidIterator.hasNext()) {
                    Map.Entry<BigDecimal, Queue<OrderRequest>> entry = bidIterator.next();
                    BigDecimal price = entry.getKey();
                    Queue<OrderRequest> queue = entry.getValue();

                    // 시장가보다 싸게 사려고 하면, 그 뒤의 더 싼 주문들은 볼 필요도 없음 (탐색 중단!)
                    if (price.compareTo(this.currentBestAsk) < 0) {
                        break;
                    }

                    // 조건 만족 시 큐 안에서 시간 순서대로(먼저 온 사람부터) 전부 체결
                    while (!queue.isEmpty()) {
                        OrderRequest bid = queue.poll();
                        trades.add(createExecutionResult(bid, EventType.MATCHED, this.currentBestAsk));
                        orderCache.remove(bid.getOrderId());
                    }
                    // 큐가 비었으면 맵에서 가격대 엔트리 삭제
                    bidIterator.remove();
                }
            }

            // 2. 대기 매도 주문 검사: 제일 싸게 판다는 사람부터 시장 매수 1호가(bestBid) 이상으로 팔 수 있는지 검사
            if (this.currentBestBid != null) {
                Iterator<Map.Entry<BigDecimal, Queue<OrderRequest>>> askIterator = pendingAsks.entrySet().iterator();
                while (askIterator.hasNext()) {
                    Map.Entry<BigDecimal, Queue<OrderRequest>> entry = askIterator.next();
                    BigDecimal price = entry.getKey();
                    Queue<OrderRequest> queue = entry.getValue();

                    // 시장가보다 비싸게 팔려고 하면, 그 뒤의 더 비싼 주문들은 볼 필요도 없음 (탐색 중단!)
                    if (price.compareTo(this.currentBestBid) > 0) {
                        break;
                    }

                    // 조건 만족 시 큐 안에서 시간 순서대로 전부 체결
                    while (!queue.isEmpty()) {
                        OrderRequest ask = queue.poll();
                        trades.add(createExecutionResult(ask, EventType.MATCHED, this.currentBestBid));
                        orderCache.remove(ask.getOrderId());
                    }
                    // 큐가 비었으면 맵에서 가격대 엔트리 삭제
                    askIterator.remove();
                }
            }

            return trades;
        } finally {
            lock.unlock();
        }
    }

    /**
     * 주문 취소 처리 (orderCache를 이용한 O(1) 탐색 최적화)
     */
    public ExecutionResult cancelOrder(Long orderId) {
        lock.lock();
        try {
            OrderRequest orderToCancel = orderCache.remove(orderId);
            if (orderToCancel == null) {
                return null; // 해당 주문이 존재하지 않거나 이미 체결됨
            }

            BigDecimal price = orderToCancel.getPrice();
            if (orderToCancel.getOrderType() == OrderType.BUY) {
                Queue<OrderRequest> queue = pendingBids.get(price);
                if (queue != null) {
                    queue.remove(orderToCancel);
                    if (queue.isEmpty()) {
                        pendingBids.remove(price);
                    }
                    log.debug("[검증 로그] 매수 주문 완전 삭제 (Cache/Queue) - 남은 총 대기 주문 수: {}", orderCache.size());
                    return createExecutionResult(orderToCancel, EventType.CANCELLED, null);
                }
            } else {
                Queue<OrderRequest> queue = pendingAsks.get(price);
                if (queue != null) {
                    queue.remove(orderToCancel);
                    if (queue.isEmpty()) {
                        pendingAsks.remove(price);
                    }
                    log.debug("[검증 로그] 매도 주문 완전 삭제 (Cache/Queue) - 남은 총 대기 주문 수: {}", orderCache.size());
                    return createExecutionResult(orderToCancel, EventType.CANCELLED, null);
                }
            }
            return null;
        } finally {
            lock.unlock();
        }
    }

    private ExecutionResult createExecutionResult(OrderRequest order, EventType eventType, BigDecimal matchPrice) {
        return ExecutionResult.builder()
                .executionId(ExecutionIdGenerator.generate())
                .orderId(order.getOrderId())
                .orderType(order.getOrderType())
                .eventType(eventType)
                .ticker(ticker)
                .matchPrice(matchPrice)
                .matchQuantity(order.getRequestedQuantity()) // 부분 체결 미지원으로 전부 취소/체결
                .executedAt(LocalDateTime.now())
                .build();
    }
}
