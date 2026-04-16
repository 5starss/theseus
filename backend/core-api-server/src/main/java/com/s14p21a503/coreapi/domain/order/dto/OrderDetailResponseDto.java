package com.s14p21a503.coreapi.domain.order.dto;

import com.s14p21a503.coreapi.domain.order.entity.Order;
import com.s14p21a503.coreapi.domain.order.entity.OrderStatus;
import com.s14p21a503.coreapi.domain.order.entity.OrderType;
import com.s14p21a503.coreapi.domain.order.entity.PriceType;
import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Getter
@Builder
public class OrderDetailResponseDto {
    private Long orderId;
    private String companyName;
    private String ticker;
    private OrderType orderType;
    private OrderStatus status;
    private PriceType priceType;
    private BigDecimal pricePerShare;
    private Integer orderQuantity;
    private BigDecimal orderAmount;
    private LocalDateTime orderCreatedAt;

    public static OrderDetailResponseDto from(Order order) {
        String companyName = order.getStock() != null ? order.getStock().getCompanyName() : order.getTicker();
        BigDecimal orderAmount = order.getPrice().multiply(BigDecimal.valueOf(order.getRequestedQuantity()));

        return OrderDetailResponseDto.builder()
                .orderId(order.getId())
                .companyName(companyName)
                .ticker(order.getTicker())
                .orderType(order.getOrderType())
                .status(order.getStatus())
                .priceType(order.getPriceType())
                .pricePerShare(order.getPrice())
                .orderQuantity(order.getRequestedQuantity())
                .orderAmount(orderAmount)
                .orderCreatedAt(order.getCreatedAt())
                .build();
    }
}
