package com.s14p21a503.coreapi.domain.account.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.s14p21a503.coreapi.domain.account.entity.AccountType;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;

@Getter
@NoArgsConstructor
public class TransferRequestDto {

    @JsonProperty("from_type")
    private AccountType fromType;

    @JsonProperty("to_type")
    private AccountType toType;

    private BigDecimal amount;
}
