package com.s14p21a503.coreapi.domain.order.dto;

import com.s14p21a503.coreapi.domain.order.entity.Order;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
public class OrderCancelEventDto {

    private Long orderId;
    private Long userId;
    private String ticker;

    @Builder
    public OrderCancelEventDto(Long orderId, Long userId, String ticker) {
        this.orderId = orderId;
        this.userId = userId;
        this.ticker = ticker;
    }

    public static OrderCancelEventDto from(Order order) {
        return OrderCancelEventDto.builder()
                .orderId(order.getId())
                .userId(order.getUserId())
                .ticker(order.getTicker())
                .build();
    }
}
