package com.s14p21a503.coreapi.domain.account.repository;

import com.s14p21a503.coreapi.domain.account.entity.AccountHistory;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import java.time.LocalDateTime;

public interface AccountHistoryRepository extends JpaRepository<AccountHistory, Long> {

    // 전체 기간 조회 (최신순)
    Page<AccountHistory> findAllByUserIdOrderByExecutedAtDesc(Long userId, Pageable pageable);

    // 특정 기간 조회 (최신순)
    Page<AccountHistory> findAllByUserIdAndExecutedAtBetweenOrderByExecutedAtDesc(
            Long userId, LocalDateTime start, LocalDateTime end, Pageable pageable);


}
