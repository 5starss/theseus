package com.s14p21a503.coreapi.domain.order.dto;

import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.math.BigDecimal;

@Getter
@Setter
@NoArgsConstructor
public class AdminForceExecuteDto {
    private int quantity;
    private BigDecimal price;
}
