package com.s14p21a503.coreapi.domain.account.dto;

import com.s14p21a503.coreapi.domain.account.entity.Account;
import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;

@Getter
@Builder
public class AccountBalanceResponseDto {
    private BigDecimal dncaTotAmt;
    private BigDecimal lockedAmt;
    private BigDecimal availableAmt;

    public static AccountBalanceResponseDto from(Account account) {
        return AccountBalanceResponseDto.builder()
                .dncaTotAmt(account.getDncaTotAmt())
                .lockedAmt(account.getLockedAmt())
                .availableAmt(account.getAvailableAmt())
                .build();

    }
}
