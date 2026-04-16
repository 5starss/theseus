package com.s14p21a503.coreapi.domain.order.repository;

import com.s14p21a503.coreapi.domain.order.entity.OrderHistory;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.time.LocalDateTime;

public interface OrderHistoryRepository extends JpaRepository<OrderHistory, Long> {

    @Query(value = "SELECT h FROM OrderHistory h JOIN FETCH h.order o LEFT JOIN FETCH o.stock " +
           "WHERE h.userId = :userId " +
           "AND (:hasAccountId = false OR h.accountId = :accountId) " +
           "AND (:ticker IS NULL OR h.ticker = :ticker) " +
           "AND (:startDate IS NULL OR h.createdAt >= :startDate) " +
           "AND (:endDate IS NULL OR h.createdAt < :endDate) " +
           "ORDER BY h.createdAt DESC",
           countQuery = "SELECT COUNT(h) FROM OrderHistory h " +
           "WHERE h.userId = :userId " +
           "AND (:hasAccountId = false OR h.accountId = :accountId) " +
           "AND (:ticker IS NULL OR h.ticker = :ticker) " +
           "AND (:startDate IS NULL OR h.createdAt >= :startDate) " +
           "AND (:endDate IS NULL OR h.createdAt < :endDate)")
    Page<OrderHistory> searchHistoryByConditions(
            @Param("userId") Long userId,
            @Param("hasAccountId") boolean hasAccountId,
            @Param("accountId") Long accountId,
            @Param("ticker") String ticker,
            @Param("startDate") LocalDateTime startDate,
            @Param("endDate") LocalDateTime endDate,
            Pageable pageable
    );
}
