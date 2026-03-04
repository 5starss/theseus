package com.s14p21a503.coreapi.domain.order.repository;

import com.s14p21a503.coreapi.domain.order.entity.Order;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import com.s14p21a503.coreapi.domain.order.entity.OrderStatus;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;
import java.util.List;

public interface OrderRepository extends JpaRepository<Order, Long> {

    @Query(value = "SELECT o FROM Order o LEFT JOIN FETCH o.stock WHERE o.userId = :userId " +
           "AND (:hasStatuses = false OR o.status IN :statuses) " +
           "AND (:ticker IS NULL OR o.ticker = :ticker) " +
           "AND (:startDate IS NULL OR o.createdAt >= :startDate) " +
           "AND (:endDate IS NULL OR o.createdAt < :endDate) " +
           "ORDER BY o.createdAt DESC",
           countQuery = "SELECT COUNT(o) FROM Order o WHERE o.userId = :userId " +
           "AND (:hasStatuses = false OR o.status IN :statuses) " +
           "AND (:ticker IS NULL OR o.ticker = :ticker) " +
           "AND (:startDate IS NULL OR o.createdAt >= :startDate) " +
           "AND (:endDate IS NULL OR o.createdAt < :endDate)")
    Page<Order> searchOrdersByConditions(
            @Param("userId") Long userId,
            @Param("hasStatuses") boolean hasStatuses,
            @Param("statuses") List<OrderStatus> statuses,
            @Param("ticker") String ticker,
            @Param("startDate") LocalDateTime startDate,
            @Param("endDate") LocalDateTime endDate,
            Pageable pageable
    );
}
