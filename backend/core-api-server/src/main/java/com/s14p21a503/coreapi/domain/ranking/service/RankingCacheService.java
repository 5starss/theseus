package com.s14p21a503.coreapi.domain.ranking.service;

import com.s14p21a503.coreapi.domain.ranking.entity.DailyRanking;
import com.s14p21a503.coreapi.domain.ranking.repository.DailyRankingRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import java.time.LocalDate;

@Service
@RequiredArgsConstructor
public class RankingCacheService {

    private final DailyRankingRepository dailyRankingRepository;

    /**
     * 특정 사용자의 특정 날짜 랭킹 정보를 캐싱합니다.
     */
    @Cacheable(value = "user_ranking", key = "#date.toString() + '_' + #userId")
    public java.util.Optional<DailyRanking> getUserRanking(LocalDate date, Long userId) {
        return dailyRankingRepository.findByRankDateAndUserId(date, userId);
    }

    /**
     * 가장 최근의 랭킹 날짜를 조회하여 캐싱합니다.
     */
    @Cacheable(value = "latest_ranking_date", key = "'LATEST'")
    public LocalDate getLatestDate() {
        return dailyRankingRepository.findTopByOrderByRankDateDesc()
                .map(DailyRanking::getRankDate)
                .orElse(LocalDate.now());
    }

    /**
     * 특정 날짜의 랭킹 페이지를 캐싱하여 반환합니다. (로컬 캐시)
     * Spring AOP 특성상 내부 호출 시 프록시가 작동하지 않으므로 별도 클래스로 분리했습니다.
     */
    @Cacheable(value = "ranking_page", key = "#date.toString() + '_' + (#nickname ?: 'ALL') + '_' + #pageable.pageNumber + '_' + #pageable.pageSize")
    public Page<DailyRanking> getRankingPage(LocalDate date, String nickname, Pageable pageable) {
        if (nickname != null && !nickname.isEmpty()) {
            return dailyRankingRepository.findAllByRankDateAndNicknameContainingOrderByRankOrderAsc(
                    date, nickname, pageable);
        } else {
            return dailyRankingRepository.findAllByRankDateOrderByRankOrderAsc(date, pageable);
        }
    }
}
