package com.s14p21a503.coreapi.domain.order.dto;

import com.s14p21a503.coreapi.domain.order.entity.OrderHistory;
import com.s14p21a503.coreapi.domain.order.entity.OrderType;
import com.s14p21a503.coreapi.domain.order.entity.PriceType;
import com.s14p21a503.coreapi.domain.order.entity.HistoryType;
import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Getter
@Builder
public class OrderHistoryDetailResponseDto {
    private Long historyId;
    private Long orderId;
    private String companyName;
    private String ticker;
    private OrderType orderType;
    private PriceType priceType;
    private HistoryType historyType;
    private BigDecimal pricePerShare;
    private Integer quantity;
    private BigDecimal totalAmount;
    private LocalDateTime orderCreatedAt;
    private LocalDateTime createdAt; // 체결 또는 취소 시간

    public static OrderHistoryDetailResponseDto from(OrderHistory history) {
        String companyName = history.getOrder().getStock() != null ? history.getOrder().getStock().getCompanyName() : history.getOrder().getTicker();
        BigDecimal totalAmount = history.getPrice() != null ? history.getPrice().multiply(BigDecimal.valueOf(history.getQuantity())) : BigDecimal.ZERO;

        return OrderHistoryDetailResponseDto.builder()
                .historyId(history.getId())
                .orderId(history.getOrder().getId())
                .companyName(companyName)
                .ticker(history.getOrder().getTicker())
                .orderType(history.getOrder().getOrderType())
                .priceType(history.getOrder().getPriceType())
                .historyType(history.getHistoryType())
                .pricePerShare(history.getPrice())
                .quantity(history.getQuantity())
                .totalAmount(totalAmount)
                .orderCreatedAt(history.getOrder().getCreatedAt())
                .createdAt(history.getCreatedAt())
                .build();
    }
}
