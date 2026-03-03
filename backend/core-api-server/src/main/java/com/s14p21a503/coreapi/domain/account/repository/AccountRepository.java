package com.s14p21a503.coreapi.domain.account.repository;

import com.s14p21a503.coreapi.domain.account.entity.Account;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.Optional;

import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

@Repository
public interface AccountRepository extends JpaRepository<Account, Long> {
    
    // 특정 회원의 계좌 정보를 찾습니다. (보통 유저 1명당 계좌 1개라고 가정)
    Optional<Account> findByUserId(Long userId);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("SELECT a FROM Account a WHERE a.userId = :userId")
    Optional<Account> findByUserIdForUpdate(@Param("userId") Long userId);
}
