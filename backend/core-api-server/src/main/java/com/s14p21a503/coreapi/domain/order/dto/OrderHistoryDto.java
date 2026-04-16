package com.s14p21a503.coreapi.domain.order.dto;

import com.s14p21a503.coreapi.domain.order.entity.OrderHistory;
import com.s14p21a503.coreapi.domain.order.entity.HistoryType;
import com.s14p21a503.coreapi.domain.order.entity.OrderType;
import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Getter
@Builder
public class OrderHistoryDto {
    private Long historyId;
    private Long orderId;
    private String ticker;
    private String companyName;
    private OrderType orderType;
    private HistoryType historyType;
    private BigDecimal price; // 체결가 또는 주문가
    private Integer quantity; // 체결량 또는 취소량
    private BigDecimal totalPrice; // price * quantity
    private LocalDateTime createdAt;

    public static OrderHistoryDto from(OrderHistory history) {
        String companyName = history.getOrder().getStock() != null ? history.getOrder().getStock().getCompanyName() : history.getOrder().getTicker();
        BigDecimal totalPrice = history.getPrice() != null ? history.getPrice().multiply(BigDecimal.valueOf(history.getQuantity())) : BigDecimal.ZERO;
        
        return OrderHistoryDto.builder()
                .historyId(history.getId())
                .orderId(history.getOrder().getId())
                .ticker(history.getOrder().getTicker())
                .companyName(companyName)
                .orderType(history.getOrder().getOrderType())
                .historyType(history.getHistoryType())
                .price(history.getPrice())
                .quantity(history.getQuantity())
                .totalPrice(totalPrice)
                .createdAt(history.getCreatedAt())
                .build();
    }
}
