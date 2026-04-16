package com.s14p21a503.coreapi.domain.position.dto;

import com.s14p21a503.coreapi.domain.position.entity.Position;
import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;

@Getter
@Builder
public class PositionResponseDto {
    private String ticker;
    private Integer quantity;
    private Integer lockedQuantity;
    private Integer availableQuantity;
    private BigDecimal averagePrice;
    private BigDecimal totalPurchaseAmount;
    private String companyName;

    public static PositionResponseDto from(Position position) {
        String companyName = position.getStock() != null
                ? position.getStock().getCompanyName()
                : position.getTicker();

        return PositionResponseDto.builder()
                .ticker(position.getTicker())
                .quantity(position.getQuantity())
                .lockedQuantity(position.getLockedQuantity())
                .availableQuantity(position.getAvailableQuantity())
                .averagePrice(position.getAveragePrice())
                .totalPurchaseAmount(position.getTotalPurchaseAmount())
                .companyName(companyName)
                .build();
    }
}
