package com.s14p21a503.coreapi.domain.order.entity;

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
@Table(name = "order_history", indexes = {
    @Index(name = "idx_orderHistory_user_created", columnList = "user_id, created_at DESC"),
    @Index(name = "idx_orderHistory_user_ticker_created", columnList = "user_id, ticker, created_at DESC")
})
public class OrderHistory {
    
    @Id @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "history_id")
    private Long id;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "order_id", nullable = false)
    private Order order;

    @Column(name = "user_id", nullable = false)
    private Long userId;

    @Column(name = "ticker", length = 20, nullable = false)
    private String ticker;

    @Enumerated(EnumType.STRING)
    @Column(name = "history_type", length = 20, nullable = false)
    private HistoryType historyType;

    @Column(name = "quantity", nullable = false)
    private Integer quantity; 

    @Column(name = "price", precision = 18, scale = 0)
    private BigDecimal price;

    @Column(name = "created_at", nullable = false)
    private LocalDateTime createdAt;

    @Builder
    public OrderHistory(Order order, Long userId, String ticker, HistoryType historyType, Integer quantity, BigDecimal price, LocalDateTime createdAt) {
        this.order = order;
        this.userId = userId;
        this.ticker = ticker;
        this.historyType = historyType;
        this.quantity = quantity;
        this.price = price;
        this.createdAt = createdAt != null ? createdAt : LocalDateTime.now();
    }
}
