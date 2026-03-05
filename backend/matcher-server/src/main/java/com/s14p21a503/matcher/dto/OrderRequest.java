package com.s14p21a503.matcher.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.ToString;

import java.math.BigDecimal;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
@ToString
public class OrderRequest {
    private String action; // "CREATE" or "CANCEL"
    private Long orderId;
    private Long accountId;
    private Long userId;
    private String ticker;
    private BigDecimal price;
    private Long requestedQuantity;
    private OrderType orderType;
    private PriceType priceType;
    private long timestamp; // 밀리초(ms) 단위의 에폭 시간
}
