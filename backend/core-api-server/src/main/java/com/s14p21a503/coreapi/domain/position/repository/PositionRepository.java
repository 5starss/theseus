package com.s14p21a503.coreapi.domain.position.repository;

import com.s14p21a503.coreapi.domain.position.entity.Position;
import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

@Repository
public interface PositionRepository extends JpaRepository<Position, Long> {
    
    // 특정 계좌에서 특정 주식 종목(ticker)에 대한 보유 포지션을 찾습니다.
    Optional<Position> findByAccountIdAndTicker(Long accountId, String ticker);

    @Query("SELECT p FROM Position p LEFT JOIN FETCH p.stock WHERE p.userId = :userId")
    List<Position> findAllWithStockByUserId(@Param("userId") Long userId);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("SELECT p FROM Position p WHERE p.accountId = :accountId AND p.ticker = :ticker")
    Optional<Position> findByAccountIdAndTickerForUpdate(@Param("accountId") Long accountId, @Param("ticker") String ticker);
}
