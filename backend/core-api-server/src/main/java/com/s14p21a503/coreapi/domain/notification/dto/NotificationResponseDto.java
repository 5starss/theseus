package com.s14p21a503.coreapi.domain.notification.dto;

import com.s14p21a503.coreapi.domain.order.entity.EventType;
import com.s14p21a503.coreapi.domain.order.entity.OrderType;

import java.math.BigDecimal;
import java.time.LocalDateTime;

public record NotificationResponseDto(
        EventType eventType,
        OrderType orderType,
        String ticker,
        BigDecimal matchPrice,
        Long matchQuantity,
        LocalDateTime executedAt
) {}
