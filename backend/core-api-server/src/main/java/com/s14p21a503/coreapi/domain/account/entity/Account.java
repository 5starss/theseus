package com.s14p21a503.coreapi.domain.account.entity;

import com.s14p21a503.coreapi.common.entity.BaseEntity;
import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.extern.slf4j.Slf4j;

import java.math.BigDecimal;

@Slf4j
@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(name = "accounts")
public class Account extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "account_id")
    private Long id;

    @Column(name = "user_id", nullable = false, unique = true)
    private Long userId;

    @Column(name = "dnca_tot_amt", precision = 18, scale = 0, nullable = false)
    private BigDecimal dncaTotAmt;

    @Column(name = "locked_amt", precision = 18, scale = 0, nullable = false)
    private BigDecimal lockedAmt = BigDecimal.ZERO;

    @Column(name = "available_amt", precision = 18, scale = 0, nullable = false)
    private BigDecimal availableAmt;

    @Builder
    public Account(Long userId, BigDecimal dncaTotAmt) {
        this.userId = userId;
        this.dncaTotAmt = dncaTotAmt != null ? dncaTotAmt : BigDecimal.ZERO;
        this.lockedAmt = BigDecimal.ZERO;
        this.availableAmt = this.dncaTotAmt;
    }

    public void lockBalance(BigDecimal amount) {
        if (this.availableAmt.compareTo(amount) < 0) {
            throw new CustomException(ErrorCode.INSUFFICIENT_BALANCE);
        }
        this.lockedAmt = this.lockedAmt.add(amount);
        this.availableAmt = this.availableAmt.subtract(amount);
    }

    public void unlockBalance(BigDecimal amount) {
        if (this.lockedAmt.compareTo(amount) < 0) {
            log.error("lockedAmt 불일치 감지 - lockedAmt: {}, unlockAmount: {}", this.lockedAmt, amount);
        }
        this.lockedAmt = this.lockedAmt.subtract(amount);
        this.availableAmt = this.availableAmt.add(amount);
    }

    public void settleBuy(BigDecimal actualCostWithFee, BigDecimal lockedCostToRelease) {
        BigDecimal refund = lockedCostToRelease.subtract(actualCostWithFee);

        this.dncaTotAmt   = this.dncaTotAmt.subtract(actualCostWithFee);
        this.lockedAmt    = this.lockedAmt.subtract(lockedCostToRelease);
        this.availableAmt = this.availableAmt.add(refund);
    }

    public void settleSell(BigDecimal netProceeds) {
        this.dncaTotAmt   = this.dncaTotAmt.add(netProceeds);
        this.availableAmt = this.availableAmt.add(netProceeds);
        // lockedAmt 변동 없음 - 매도는 주식 수량만 잠금, 금액 잠금 없음
    }
}
