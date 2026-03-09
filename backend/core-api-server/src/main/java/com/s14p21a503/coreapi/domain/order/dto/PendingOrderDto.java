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
public class PendingOrderDto {
    private Long orderId;
    private String ticker;
    private String companyName;
    private OrderType orderType;
    private OrderStatus status;
    private BigDecimal totalPrice;
    private Integer unexecutedQuantity;
    private LocalDateTime createdAt;

    public static PendingOrderDto from(Order order) {
        String companyName = order.getStock() != null ? order.getStock().getCompanyName() : order.getTicker();
        int unexecutedQuantity = order.getRequestedQuantity() - order.getExecutedQuantity();
        BigDecimal totalPrice = order.getPrice().multiply(BigDecimal.valueOf(unexecutedQuantity));
        return PendingOrderDto.builder()
                .orderId(order.getId())
                .ticker(order.getTicker())
                .companyName(companyName)
                .orderType(order.getOrderType())
                .status(order.getStatus())
                .totalPrice(totalPrice)
                .unexecutedQuantity(unexecutedQuantity)
                .createdAt(order.getCreatedAt())
                .build();
    }
}
