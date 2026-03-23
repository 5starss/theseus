package com.s14p21a503.coreapi.domain.watchlist.repository;

import com.s14p21a503.coreapi.domain.watchlist.entity.Watchlist;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

public interface WatchlistRepository extends JpaRepository<Watchlist, Long> {

    boolean existsByUserIdAndTicker(Long userId, String ticker);

    Optional<Watchlist> findByUserIdAndTicker(Long userId, String ticker);

    @Query("""
            SELECT w
            FROM Watchlist w
            JOIN FETCH w.stock
            WHERE w.userId = :userId
            ORDER BY w.createdAt DESC, w.id DESC
            """)
    List<Watchlist> findAllWithStockByUserId(@Param("userId") Long userId);
}
