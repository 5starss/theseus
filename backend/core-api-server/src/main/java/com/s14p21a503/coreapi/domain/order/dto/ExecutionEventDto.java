package com.s14p21a503.coreapi.domain.order.dto;

import com.s14p21a503.coreapi.domain.order.entity.EventType;
import com.s14p21a503.coreapi.domain.order.entity.OrderType;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class ExecutionEventDto {

    private Long executionId;           // matcher-server에서 생성한 ID (중복 처리 방지)
    private Long orderId;               // 대상 주문 ID
    private Long accountId;
    private Long userId;
    private OrderType orderType;        // BUY or SELL
    private EventType eventType;        // MATCHED, CANCELLED
    private String ticker;
    private BigDecimal matchPrice;      //취소된 경우 null
    private Long matchQuantity;
    private Long remainingQuantity;
    private LocalDateTime executedAt;

    @Builder
    public ExecutionEventDto(Long executionId, Long orderId, Long accountId, Long userId,
                             OrderType orderType, EventType eventType,
                             String ticker, BigDecimal matchPrice, Long matchQuantity, Long remainingQuantity, LocalDateTime executedAt) {
        this.executionId = executionId;
        this.orderId = orderId;
        this.accountId = accountId;
        this.userId = userId;
        this.orderType = orderType;
        this.eventType = eventType;
        this.ticker = ticker;
        this.matchPrice = matchPrice;
        this.matchQuantity = matchQuantity;
        this.remainingQuantity = remainingQuantity;
        this.executedAt = executedAt;
    }
}
