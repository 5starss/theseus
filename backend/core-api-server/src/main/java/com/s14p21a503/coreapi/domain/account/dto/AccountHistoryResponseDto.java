package com.s14p21a503.coreapi.domain.account.dto;

import com.s14p21a503.coreapi.common.response.PageResponseDto;
import com.s14p21a503.coreapi.domain.account.entity.AccountHistory;
import com.s14p21a503.coreapi.domain.account.entity.TransactionType;
import lombok.Builder;
import lombok.Getter;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Getter
@Builder
public class AccountHistoryResponseDto {

    private Integer year;
    private Integer month;
    private PageResponseDto<HistoryDto> histories;

    @Getter
    @Builder
    public static class HistoryDto {
        private Long historyId;
        private TransactionType transactionType;
        private LocalDateTime executedAt;
        private String ticker;
        private String stockName;
        private int quantity;
        private BigDecimal price;
        private BigDecimal fee;
        private BigDecimal tax;
        private BigDecimal amount;
        private BigDecimal balanceAfter;

        public static HistoryDto from(AccountHistory history) {
            return HistoryDto.builder()
                    .historyId(history.getId())
                    .transactionType(history.getTransactionType())
                    .executedAt(history.getExecutedAt())
                    .ticker(history.getTicker())
                    .stockName(history.getStockName())
                    .quantity(history.getQuantity())
                    .price(history.getPrice())
                    .fee(history.getFee())
                    .tax(history.getTax())
                    .amount(history.getAmount())
                    .balanceAfter(history.getBalanceAfter())
                    .build();
        }
    }
}
