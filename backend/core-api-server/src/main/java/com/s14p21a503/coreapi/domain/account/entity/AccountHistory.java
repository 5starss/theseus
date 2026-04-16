package com.s14p21a503.coreapi.domain.account.entity;

import com.s14p21a503.coreapi.common.entity.BaseEntity;
import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(name = "account_histories", indexes = {
    @Index(name = "idx_accountHistory_account_executed", columnList = "account_id, executed_at DESC")
})
public class AccountHistory extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "history_id")
    private Long id;

    @Column(name = "account_id", nullable = false)
    private Long accountId;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Enumerated(EnumType.STRING)
    @Column(name = "transaction_type", nullable = false)
    private TransactionType transactionType;

    @Column(name = "ticker")
    private String ticker;

    @Column(name = "stock_name")
    private String stockName;

    @Column(name = "quantity", nullable = false)
    private int quantity = 0;

    @Column(name = "price", precision = 18, scale = 0)
    private BigDecimal price;

    @Column(name = "fee", precision = 18, scale = 0, nullable = true)
    private BigDecimal fee = BigDecimal.ZERO;

    @Column(name = "tax", precision = 18, scale = 0, nullable = true)
    private BigDecimal tax = BigDecimal.ZERO;

    @Column(name = "amount", precision = 18, scale = 0, nullable = false)
    private BigDecimal amount; // 실질 정산 금액 (수수료, 세금 반영 후)

    @Column(name = "balance_after", precision = 18, scale = 0, nullable = false)
    private BigDecimal balanceAfter; // 거래 후 원장 잔액

    @Column(name = "executed_at", nullable = false)
    private LocalDateTime executedAt;

    @Builder
    public AccountHistory(Long accountId, Long userId, TransactionType transactionType, String ticker, String stockName,
                          int quantity, BigDecimal price, BigDecimal fee, BigDecimal tax,
                          BigDecimal amount, BigDecimal balanceAfter, LocalDateTime executedAt) {
        this.accountId = accountId;
        this.userId = userId;
        this.transactionType = transactionType;
        this.ticker = ticker;
        this.stockName = stockName;
        this.quantity = quantity;
        this.price = price;
        this.fee = fee != null ? fee : BigDecimal.ZERO;
        this.tax = tax != null ? tax : BigDecimal.ZERO;
        this.amount = amount;
        this.balanceAfter = balanceAfter;
        this.executedAt = executedAt;
    }
}
