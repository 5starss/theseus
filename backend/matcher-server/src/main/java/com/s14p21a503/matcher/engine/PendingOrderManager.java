package com.s14p21a503.matcher.engine;

import com.s14p21a503.matcher.dto.*;
import com.s14p21a503.matcher.journal.SnapshotState;
import com.s14p21a503.matcher.util.ExecutionIdGenerator;
import lombok.Getter;
import lombok.extern.slf4j.Slf4j;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.locks.ReentrantLock;

@Slf4j
public class PendingOrderManager {

    @Getter
    private final String ticker;
    private final ExecutionIdGenerator executionIdGenerator;

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

    // 서비스 참여율 (시장 거래량의 몇 %를 우리 서비스 유동성으로 가져올지 정의)
    private final BigDecimal participationRate;

    // 유동성 소수점 적립금 (버려지는 유동성 방지)
    private BigDecimal liquidityRemainder = BigDecimal.ZERO;

    public PendingOrderManager(String ticker, ExecutionIdGenerator executionIdGenerator, BigDecimal participationRate) {
        this.ticker = ticker;
        this.executionIdGenerator = executionIdGenerator;
        this.participationRate = participationRate;
    }

    /**
     * 주문 추가 (대기열에 추가)
     * 이제 즉시 체결 로직은 matchWithTick에서 담당하므로 여기서는 큐에 넣기만 함
     */
    public List<ExecutionResult> addOrder(OrderRequest order) {
        lock.lock();
        try {
            // 멱등성 보장: 이미 존재하는 주문이면 무시 (복구 리플레이 또는 카프카 재전송 대비)
            if (orderCache.containsKey(order.getOrderId())) {
                log.debug("[{}] 이미 대기열에 존재하는 주문입니다 (OrderID: {})", ticker, order.getOrderId());
                return new ArrayList<>();
            }

            // 새로 들어온 주문이면 remainingQuantity 초기화
            if (order.getRemainingQuantity() == null) {
                order.setRemainingQuantity(order.getRequestedQuantity());
            }

            if (order.getOrderType() == OrderType.BUY) {
                pendingBids.computeIfAbsent(order.getPrice(), k -> new LinkedList<>()).add(order);
            } else if (order.getOrderType() == OrderType.SELL) {
                pendingAsks.computeIfAbsent(order.getPrice(), k -> new LinkedList<>()).add(order);
            }
            orderCache.put(order.getOrderId(), order);

            return new ArrayList<>(); // 즉시 체결은 틱이 올 때 수행됨
        } finally {
            lock.unlock();
        }
    }

    /**
     * 시세 업데이트 수신 시, 최우선 호가 정보만 갱신
     */
    public void updateMarketData(MarketDataEvent event) {
        lock.lock();
        try {
            this.currentBestBid = event.getBidPrice1();
            this.currentBestAsk = event.getAskPrice1();
        } finally {
            lock.unlock();
        }
    }

    /**
     * 시장 체결(Tick) 데이터 수신 시, 대기 주문들과 매칭 수행
     */
    public List<ExecutionResult> matchWithTick(TickDataEvent tick, long currentSeqNo) {
        lock.lock();
        try {
            List<ExecutionResult> trades = new ArrayList<>();

            // 사용할 수 있는 시장 유동성 계산: tick.volume * participationRate
            BigDecimal rawLiquidity = new BigDecimal(tick.getAccVol())
                    .multiply(participationRate)
                    .add(liquidityRemainder);

            // 정수 부분만 이번 유동성으로 사용
            long usableLiquidity = rawLiquidity.setScale(0, RoundingMode.DOWN).longValue();

            // 남은 소수점 부분은 다음을 위해 다시 적립
            this.liquidityRemainder = rawLiquidity.subtract(new BigDecimal(usableLiquidity));

            if (usableLiquidity <= 0) {
                return trades;
            }

            // 1. 대기 매수 주문 검사 (매수 주문 vs 시장 매도 틱)
            // 매수 조건: bestAsk <= limitPrice
            if (this.currentBestAsk != null) {
                Iterator<Map.Entry<BigDecimal, Queue<OrderRequest>>> bidIterator = pendingBids.entrySet().iterator();
                int fillIndex = 0;
                while (bidIterator.hasNext() && usableLiquidity > 0) {
                    Map.Entry<BigDecimal, Queue<OrderRequest>> entry = bidIterator.next();
                    BigDecimal limitPrice = entry.getKey();
                    Queue<OrderRequest> queue = entry.getValue();

                    // 조건: 최우선 매도호가(bestAsk)가 내 지정가(limitPrice)보다 높으면 살 수 없음
                    if (this.currentBestAsk.compareTo(limitPrice) > 0) {
                        break;
                    }

                    Iterator<OrderRequest> queueIterator = queue.iterator();
                    while (queueIterator.hasNext() && usableLiquidity > 0) {
                        OrderRequest bid = queueIterator.next();

                        long fillQty = Math.min(bid.getRemainingQuantity(), usableLiquidity);
                        if (fillQty > 0) {
                            bid.setRemainingQuantity(bid.getRemainingQuantity() - fillQty);
                            usableLiquidity -= fillQty;

                            trades.add(createExecutionResult(bid, fillQty, this.currentBestAsk, currentSeqNo, fillIndex++));

                            if (bid.getRemainingQuantity() == 0) {
                                orderCache.remove(bid.getOrderId());
                                queueIterator.remove();
                            }
                        }
                    }
                    if (queue.isEmpty()) {
                        bidIterator.remove();
                    }
                }
            }

            // 유동성이 남았다면 매도 주문도 검사
            if (usableLiquidity <= 0)
                return trades;

            // 2. 대기 매도 주문 검사 (매도 주문 vs 시장 매수 틱)
            // 매도 조건: bestBid >= limitPrice
            if (this.currentBestBid != null) {
                Iterator<Map.Entry<BigDecimal, Queue<OrderRequest>>> askIterator = pendingAsks.entrySet().iterator();
                int fillIndex = 0;
                while (askIterator.hasNext() && usableLiquidity > 0) {
                    Map.Entry<BigDecimal, Queue<OrderRequest>> entry = askIterator.next();
                    BigDecimal limitPrice = entry.getKey();
                    Queue<OrderRequest> queue = entry.getValue();

                    // 조건: 최우선 매수호가(bestBid)가 내 지정가(limitPrice)보다 낮으면 팔 수 없음
                    if (this.currentBestBid.compareTo(limitPrice) < 0) {
                        break;
                    }

                    Iterator<OrderRequest> queueIterator = queue.iterator();
                    while (queueIterator.hasNext() && usableLiquidity > 0) {
                        OrderRequest ask = queueIterator.next();

                        long fillQty = Math.min(ask.getRemainingQuantity(), usableLiquidity);
                        if (fillQty > 0) {
                            ask.setRemainingQuantity(ask.getRemainingQuantity() - fillQty);
                            usableLiquidity -= fillQty;

                            trades.add(createExecutionResult(ask, fillQty, this.currentBestBid, currentSeqNo, fillIndex++));

                            if (ask.getRemainingQuantity() == 0) {
                                orderCache.remove(ask.getOrderId());
                                queueIterator.remove();
                            }
                        }
                    }
                    if (queue.isEmpty()) {
                        askIterator.remove();
                    }
                }
            }

            return trades;
        } finally {
            lock.unlock();
        }
    }

    /**
     * [복구 전용] 매칭 로직을 실행하지 않고 유동성 적립금만 업데이트합니다.
     * 이미 체결 결과(RES)가 존재하거나 COMMIT된 틱에 대해 상태 드리프트를 방지하기 위해 사용합니다.
     */
    public void updateLiquidityRemainderOnly(TickDataEvent tick) {
        lock.lock();
        try {
            BigDecimal rawLiquidity = new BigDecimal(tick.getAccVol())
                    .multiply(participationRate)
                    .add(liquidityRemainder);
            long usableLiquidity = rawLiquidity.setScale(0, RoundingMode.DOWN).longValue();
            this.liquidityRemainder = rawLiquidity.subtract(new BigDecimal(usableLiquidity));
        } finally {
            lock.unlock();
        }
    }

    /**
     * 주문 취소 처리
     */
    public ExecutionResult cancelOrder(Long orderId, long currentSeqNo) {
        lock.lock();
        try {
            OrderRequest orderToCancel = orderCache.remove(orderId);
            if (orderToCancel == null) {
                return null;
            }

            BigDecimal price = orderToCancel.getPrice();
            if (orderToCancel.getOrderType() == OrderType.BUY) {
                Queue<OrderRequest> queue = pendingBids.get(price);
                if (queue != null) {
                    queue.remove(orderToCancel);
                    if (queue.isEmpty()) {
                        pendingBids.remove(price);
                    }
                    return createExecutionResult(orderToCancel, EventType.CANCELLED, null, 0L, currentSeqNo, 0);
                }
            } else {
                Queue<OrderRequest> queue = pendingAsks.get(price);
                if (queue != null) {
                    queue.remove(orderToCancel);
                    if (queue.isEmpty()) {
                        pendingAsks.remove(price);
                    }
                    return createExecutionResult(orderToCancel, EventType.CANCELLED, null, 0L, currentSeqNo, 0);
                }
            }
            return null;
        } finally {
            lock.unlock();
        }
    }

    /**
     * 과거 체결 결과(RES)를 강제로 상태에 반영 (복귀 시 사용).
     * 엔진의 매칭 로직을 타지 않고, 기록된 결과대로 오더북 잔량을 차감합니다.
     */
    public void applyExecutionResult(ExecutionResult res) {
        lock.lock();
        try {
            OrderRequest order = orderCache.get(res.getOrderId());
            if (order == null) {
                log.warn("[{}] 복구 중 결과를 적용할 주문을 찾지 못함 (OrderID: {})", ticker, res.getOrderId());
                return;
            }

            // 잔량 차감
            long currentQty = order.getRemainingQuantity();
            long executedQty = res.getMatchQuantity();
            order.setRemainingQuantity(Math.max(0, currentQty - executedQty));

            // 잔량이 0이면 오더북에서 제거
            if (order.getRemainingQuantity() == 0) {
                orderCache.remove(order.getOrderId());
                BigDecimal price = order.getPrice();
                if (order.getOrderType() == OrderType.BUY) {
                    Queue<OrderRequest> queue = pendingBids.get(price);
                    if (queue != null) {
                        queue.remove(order);
                        if (queue.isEmpty()) pendingBids.remove(price);
                    }
                } else {
                    Queue<OrderRequest> queue = pendingAsks.get(price);
                    if (queue != null) {
                        queue.remove(order);
                        if (queue.isEmpty()) pendingAsks.remove(price);
                    }
                }
            }
        } finally {
            lock.unlock();
        }
    }

    /**
     * 현재 오더북 상태 캡처 (스냅샷용).
     */
    public SnapshotState.SnapshotStateBuilder fillSnapshotBuilder(SnapshotState.SnapshotStateBuilder builder) {
        lock.lock();
        try {
            return builder
                    .pendingBids(new TreeMap<>(pendingBids))
                    .pendingAsks(new TreeMap<>(pendingAsks))
                    .orderCache(new HashMap<>(orderCache))
                    .currentBestBid(currentBestBid)
                    .currentBestAsk(currentBestAsk)
                    .liquidityRemainder(liquidityRemainder);
        } finally {
            lock.unlock();
        }
    }

    /**
     * 스냅샷 상태로부터 오더북 복원.
     */
    public void restoreState(SnapshotState state) {
        lock.lock();
        try {
            this.pendingBids.clear();
            this.pendingBids.putAll(state.getPendingBids());
            this.pendingAsks.clear();
            this.pendingAsks.putAll(state.getPendingAsks());
            this.orderCache.clear();
            this.orderCache.putAll(state.getOrderCache());
            this.currentBestBid = state.getCurrentBestBid();
            this.currentBestAsk = state.getCurrentBestAsk();
            this.liquidityRemainder = state.getLiquidityRemainder() != null ? state.getLiquidityRemainder() : BigDecimal.ZERO;
            log.info("[{}] 오더북 상태 복원 완료 - 매수: {}, 매도: {}, 캐시: {}",
                    ticker, pendingBids.size(), pendingAsks.size(), orderCache.size());
        } finally {
            lock.unlock();
        }
    }

    /**
     * 모든 미체결 주문 일괄 취소 처리
     */
    public List<ExecutionResult> cancelAllOrders(long currentSeqNo) {
        lock.lock();
        try {
            List<ExecutionResult> cancelResults = new ArrayList<>();
            int fillIndex = 0;

            // orderCache에 있는 모든 주문을 순회하며 취소 결과 생성
            for (OrderRequest order : orderCache.values()) {
                cancelResults.add(createExecutionResult(order, EventType.CANCELLED, null, 0L, currentSeqNo, fillIndex++));
            }

            // 모든 자료구조 초기화
            orderCache.clear();
            pendingBids.clear();
            pendingAsks.clear();

            log.info("[{}] 정규장 마감으로 인한 모든 미체결 주문 일괄 취소 처리 완료 (취소 건수: {})", ticker, cancelResults.size());
            return cancelResults;
        } finally {
            lock.unlock();
        }
    }

    private ExecutionResult createExecutionResult(OrderRequest order, long fillQty, BigDecimal matchPrice, long seqNo, int fillIndex) {
        return createExecutionResult(order, EventType.MATCHED, matchPrice, fillQty, seqNo, fillIndex);
    }

    private ExecutionResult createExecutionResult(OrderRequest order, EventType eventType, BigDecimal matchPrice,
            long fillQty, long seqNo, int fillIndex) {
        return ExecutionResult.builder()
                .executionId(executionIdGenerator.generate(seqNo, fillIndex))
                .orderId(order.getOrderId())
                .accountId(order.getAccountId())
                .userId(order.getUserId())
                .orderType(order.getOrderType())
                .eventType(eventType)
                .ticker(ticker)
                .matchPrice(matchPrice)
                .matchQuantity(fillQty)
                .executedAt(LocalDateTime.now())
                .build();
    }
}
