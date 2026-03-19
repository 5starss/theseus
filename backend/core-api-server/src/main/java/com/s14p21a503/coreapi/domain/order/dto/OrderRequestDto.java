package com.s14p21a503.coreapi.domain.order.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.s14p21a503.coreapi.domain.account.entity.AccountType;
import com.s14p21a503.coreapi.domain.order.entity.OrderType;
import com.s14p21a503.coreapi.domain.order.entity.PriceType;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

@Getter
@NoArgsConstructor
public class OrderRequestDto {
    private String ticker;

    @JsonProperty("order_type")
    private OrderType orderType;

    @JsonProperty("price_type")
    private PriceType priceType = PriceType.LIMIT; // MVP 시 지정가가 기본값, 추후 시장가(MARKET) 확장 가능

    @JsonProperty("account_type")
    private AccountType accountType = AccountType.USER;

    private BigDecimal price;
    private Integer quantity;
}
