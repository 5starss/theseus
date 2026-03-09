package com.s14p21a503.coreapi.domain.order.entity;

import jakarta.persistence.*;
import lombok.AccessLevel;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import org.springframework.data.domain.Persistable;

import java.math.BigDecimal;
import java.time.LocalDateTime;

@Entity
@Getter
@NoArgsConstructor(access = AccessLevel.PROTECTED)
@Table(name = "executions")
public class Execution implements Persistable<Long> {

    @Id
    @Column(name = "execution_id")
    private Long id;

    @Override
    public boolean isNew() {
        return true;
    }

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "order_id", nullable = false)
    private Order order;

    @Column(name = "execution_price", precision = 18, scale = 0, nullable = false)
    private BigDecimal executionPrice;

    @Column(name = "execution_quantity", nullable = false)
    private Integer executionQuantity;

    @Column(name = "executed_at", nullable = false)
    private LocalDateTime executedAt;

    @Builder
    public Execution(Long id, Order order, BigDecimal executionPrice, Integer executionQuantity,
            LocalDateTime executedAt) {
        this.id = id;
        this.order = order;
        this.executionPrice = executionPrice;
        this.executionQuantity = executionQuantity;
        this.executedAt = executedAt != null ? executedAt : LocalDateTime.now();
    }
}
