package com.s14p21a503.coreapi.domain.order.dto;

import com.s14p21a503.coreapi.domain.order.entity.Order;
import com.s14p21a503.coreapi.domain.order.entity.OrderType;
import com.s14p21a503.coreapi.domain.order.entity.PriceType;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class OrderEventDto {

    private Long orderId;
    private Long accountId;
    private Long userId;
    private String ticker;
    private OrderType orderType;
    private PriceType priceType;
    private BigDecimal price;
    private Integer requestedQuantity;

    @Builder
    public OrderEventDto(Long orderId, Long accountId, Long userId, String ticker, OrderType orderType, PriceType priceType, BigDecimal price, Integer requestedQuantity) {
        this.orderId = orderId;
        this.accountId = accountId;
        this.userId = userId;
        this.ticker = ticker;
        this.orderType = orderType;
        this.priceType = priceType;
        this.price = price;
        this.requestedQuantity = requestedQuantity;
    }

    public static OrderEventDto from(Order order) {
        return OrderEventDto.builder()
                .orderId(order.getId())
                .accountId(order.getAccountId())
                .userId(order.getUserId())
                .ticker(order.getTicker())
                .orderType(order.getOrderType())
                .priceType(order.getPriceType())
                .price(order.getPrice())
                .requestedQuantity(order.getRequestedQuantity())
                .build();
    }
}
