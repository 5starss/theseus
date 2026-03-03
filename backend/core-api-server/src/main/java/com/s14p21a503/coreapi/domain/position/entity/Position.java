package com.s14p21a503.coreapi.domain.position.entity;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@EntityListeners(AuditingEntityListener.class)
@Table(name = "positions")
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

    @Column(name = "quantity", nullable = false)
    private Integer quantity;

    @Column(name = "locked_quantity", nullable = false)
    private Integer lockedQuantity = 0;

    @Column(name = "available_quantity", nullable = false)
    private Integer availableQuantity;

    @Column(name = "average_price", precision = 18, scale = 2, nullable = false)
    private BigDecimal averagePrice;

    @LastModifiedDate
    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    @Builder
    public Position(Long accountId, Long userId, String ticker, Integer quantity, BigDecimal averagePrice) {
        this.accountId = accountId;
        this.userId = userId;
        this.ticker = ticker;
        this.quantity = quantity;
        this.lockedQuantity = 0;
        this.availableQuantity = quantity != null ? quantity : 0;
        this.averagePrice = averagePrice;
    }

    public void lockQuantity(Integer amount) {
        if (this.availableQuantity < amount) {
            throw new CustomException(ErrorCode.INSUFFICIENT_QUANTITY);
        }
        this.lockedQuantity += amount;
        this.availableQuantity -= amount;
    }
}
