package com.s14p21a503.coreapi.domain.order.dto;

import com.s14p21a503.coreapi.domain.order.entity.TradePolicy;
import lombok.Getter;

import java.math.BigDecimal;

@Getter
public class TradePolicyResponseDto {

    private final BigDecimal feeRate;
    private final BigDecimal taxRate;

    private TradePolicyResponseDto() {
        this.feeRate = TradePolicy.FEE_RATE;
        this.taxRate = TradePolicy.TAX_RATE;
    }

    public static TradePolicyResponseDto of() {
        return new TradePolicyResponseDto();
    }
}
