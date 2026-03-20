package com.s14p21a503.coreapi.domain.ranking.repository;

import com.s14p21a503.coreapi.domain.ranking.entity.DailyRanking;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Modifying;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.time.LocalDate;
import java.util.Optional;

@Repository
public interface DailyRankingRepository extends JpaRepository<DailyRanking, Long> {
    
    Optional<DailyRanking> findTopByOrderByRankDateDesc();

    Page<DailyRanking> findAllByRankDateOrderByRankOrderAsc(LocalDate rankDate, Pageable pageable);

    @Query(nativeQuery = true, 
           value = "SELECT * FROM daily_rankings " +
                   "WHERE rank_date = :rankDate " +
                   "AND MATCH(nickname) AGAINST(:nickname IN BOOLEAN MODE) " +
                   "ORDER BY rank_order ASC",
           countQuery = "SELECT count(*) FROM daily_rankings " +
                        "WHERE rank_date = :rankDate " +
                        "AND MATCH(nickname) AGAINST(:nickname IN BOOLEAN MODE)")
    Page<DailyRanking> findAllByRankDateAndNicknameContainingOrderByRankOrderAsc(@Param("rankDate") LocalDate rankDate, @Param("nickname") String nickname, Pageable pageable);

    Optional<DailyRanking> findByRankDateAndUserId(LocalDate rankDate, Long userId);

    @Modifying(clearAutomatically = true)
    @Query("DELETE FROM DailyRanking d WHERE d.rankDate = :rankDate")
    void deleteAllByRankDate(@Param("rankDate") LocalDate rankDate);
}
