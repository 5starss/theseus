package com.s14p21a503.coreapi.domain.order.dto;

import com.s14p21a503.coreapi.domain.order.entity.Order;
import com.s14p21a503.coreapi.domain.order.entity.OrderStatus;
import com.s14p21a503.coreapi.domain.order.entity.OrderType;
import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Getter
@Builder
public class OrderResponseDto {
    private Long orderId;
    private OrderStatus status;
    private Integer requestedQuantity;
    private Integer executedQuantity;
    private BigDecimal price;
    private String ticker;
    private OrderType orderType;
    private LocalDateTime createdAt;

    public static OrderResponseDto from(Order order) {
        return OrderResponseDto.builder()
                .orderId(order.getId())
                .status(order.getStatus())
                .requestedQuantity(order.getRequestedQuantity())
                .executedQuantity(order.getExecutedQuantity())
                .price(order.getPrice())
                .ticker(order.getTicker())
                .orderType(order.getOrderType())
                .createdAt(order.getCreatedAt())
                .build();
    }
}
