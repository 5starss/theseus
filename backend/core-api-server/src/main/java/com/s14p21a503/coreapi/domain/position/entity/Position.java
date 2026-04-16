package com.s14p21a503.coreapi.domain.position.entity;

import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import com.s14p21a503.coreapi.domain.stock.entity.Stock;
import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import java.math.BigDecimal;
import java.math.RoundingMode;
import java.time.LocalDateTime;

@Slf4j
@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@EntityListeners(AuditingEntityListener.class)
@Table(name = "positions",
        uniqueConstraints = @UniqueConstraint(
                name = "uk_positions_account_ticker",
                columnNames = {"account_id", "ticker"}
        )
)
public class Position {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "position_id")
    private Long id;

    @Column(name = "account_id", nullable = false)
    private Long accountId;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Column(name = "ticker", length = 20, nullable = false)
    private String ticker;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "ticker", referencedColumnName = "ticker", insertable = false, updatable = false)
    private Stock stock;

    @Column(name = "quantity", nullable = false)
    private Integer quantity;

    @Column(name = "locked_quantity", nullable = false)
    private Integer lockedQuantity = 0;

    @Column(name = "available_quantity", nullable = false)
    private Integer availableQuantity;

    @Column(name = "average_price", precision = 18, scale = 0, nullable = false)
    private BigDecimal averagePrice;

    @Column(name = "total_purchase_amount", precision = 18, scale = 0, nullable = false)
    private BigDecimal totalPurchaseAmount;

    @LastModifiedDate
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    @Builder
    public Position(Long accountId, Long userId, String ticker, Integer quantity, BigDecimal averagePrice, BigDecimal totalPurchaseAmount) {
        this.accountId = accountId;
        this.userId = userId;
        this.ticker = ticker;
        this.quantity = quantity;
        this.lockedQuantity = 0;
        this.availableQuantity = quantity != null ? quantity : 0;
        this.averagePrice = averagePrice;
        this.totalPurchaseAmount =  totalPurchaseAmount;
    }

    public void lockQuantity(int amount) {
        if (this.availableQuantity < amount) {
            throw new CustomException(ErrorCode.INSUFFICIENT_QUANTITY);
        }
        this.lockedQuantity += amount;
        this.availableQuantity -= amount;
    }

    public void unlockQuantity(int amount) {
        if (this.lockedQuantity < amount) {
            log.error("lockedQuantity 불일치 감지 - lockedQuantity: {}, unlockAmount: {}", this.lockedQuantity, amount);
        }
        this.lockedQuantity -= amount;
        this.availableQuantity += amount;
    }

    public void applyBuy(int quantity, BigDecimal executionPrice) {
        BigDecimal newPurchaseAmt  = executionPrice.multiply(BigDecimal.valueOf(quantity));
        BigDecimal newTotalPurchase = this.totalPurchaseAmount.add(newPurchaseAmt);
        int newQuantity = this.quantity + quantity;

        this.averagePrice        = newTotalPurchase.divide(BigDecimal.valueOf(newQuantity), 0, RoundingMode.HALF_UP);
        this.totalPurchaseAmount = newTotalPurchase;
        this.quantity            = newQuantity;
        this.availableQuantity   += quantity;
    }

    public void applySell(int quantity) {
        this.totalPurchaseAmount = this.totalPurchaseAmount
                .subtract(this.averagePrice.multiply(BigDecimal.valueOf(quantity)));
        this.quantity       -= quantity;
        this.lockedQuantity -= quantity;
        // quantity == 0이면 Position 삭제는 Service에서 처리
    }
}
