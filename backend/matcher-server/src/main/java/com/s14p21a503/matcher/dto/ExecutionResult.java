package com.s14p21a503.matcher.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.ToString;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
@ToString
public class ExecutionResult {
    private Long executionId;     // DB 인덱싱 성능을 위한 순차적인 Long 형태의 고유 체결 번호
    private Long orderId;         // 대상 주문 ID
    private OrderType orderType;  // BUY, SELL
    private EventType eventType;  // MATCHED, CANCELLED
    private String ticker;
    private BigDecimal matchPrice; //취소된 경우 null
    private Long matchQuantity;
    private LocalDateTime executedAt;
}
