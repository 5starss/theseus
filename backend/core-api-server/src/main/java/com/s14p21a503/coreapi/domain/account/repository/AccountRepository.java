package com.s14p21a503.coreapi.domain.account.repository;

import com.s14p21a503.coreapi.domain.account.entity.Account;
import com.s14p21a503.coreapi.domain.account.entity.AccountType;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

import jakarta.persistence.LockModeType;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

@Repository
public interface AccountRepository extends JpaRepository<Account, Long> {
    
    // 특정 회원의 계좌 정보를 타입별로 찾습니다.
    Optional<Account> findByUserIdAndAccountType(Long userId, AccountType accountType);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("SELECT a FROM Account a WHERE a.userId = :userId AND a.accountType = :accountType")
    Optional<Account> findByUserIdAndAccountTypeForUpdate(@Param("userId") Long userId, @Param("accountType") AccountType accountType);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("SELECT a FROM Account a WHERE a.userId = :userId AND a.accountType IN :accountTypes ORDER BY a.id ASC")
    List<Account> findAllByUserIdAndAccountTypesForUpdate(
            @Param("userId") Long userId, 
            @Param("accountTypes") List<AccountType> accountTypes);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @Query("SELECT a FROM Account a WHERE a.id = :id")
    Optional<Account> findByIdForUpdate(@Param("id") Long id);

    // 하위 호환성을 위해 유지하거나 모든 계좌를 찾는 용도로 변경 가능
    List<Account> findAllByUserId(Long userId);
}
