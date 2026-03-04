package com.s14p21a503.coreapi.domain.order.entity;

import com.s14p21a503.coreapi.common.entity.BaseEntity;
import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import com.s14p21a503.coreapi.domain.stock.entity.Stock;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.List;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(name = "orders", indexes = {
    @Index(name = "idx_orders_user_created", columnList = "user_id, created_at DESC"),
    @Index(name = "idx_orders_user_ticker_created", columnList = "user_id, ticker, created_at DESC")
})
public class Order extends BaseEntity {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "order_id")
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

    @Enumerated(EnumType.STRING)
    @Column(name = "order_type", length = 10, nullable = false)
    private OrderType orderType; // BUY, SELL

    @Enumerated(EnumType.STRING)
    @Column(name = "price_type", length = 10, nullable = false)
    private PriceType priceType; // LIMIT(지정가), MARKET(시장가)

    @Column(name = "price", precision = 18, scale = 0, nullable = false)
    private BigDecimal price;

    @Column(name = "requested_quantity", nullable = false)
    private Integer requestedQuantity;

    @Column(name = "executed_quantity", nullable = false)
    private Integer executedQuantity;

    @Enumerated(EnumType.STRING)
    @Column(name = "status", length = 20, nullable = false)
    private OrderStatus status; // OPEN, PARTIAL, FILLED, CANCELLED

    @Builder
    public Order(Long accountId, Long userId, String ticker, OrderType orderType, PriceType priceType, BigDecimal price, Integer requestedQuantity) {
        this.accountId = accountId;
        this.userId = userId;
        this.ticker = ticker;
        this.orderType = orderType;
        this.priceType = priceType;
        this.price = price;
        this.requestedQuantity = requestedQuantity;
        this.executedQuantity = 0; // 초기 체결 수량은 0
        this.status = OrderStatus.OPEN; // 초기 상태는 OPEN(주문 접수)
    }

    public void cancel() {
        this.status = OrderStatus.CANCELLED;
    }

    public void pendingCancel() {
        this.status = OrderStatus.PENDING_CANCEL;
    }
}
