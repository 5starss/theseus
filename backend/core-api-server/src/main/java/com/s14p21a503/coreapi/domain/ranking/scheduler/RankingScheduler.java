package com.s14p21a503.coreapi.domain.ranking.scheduler;

import com.s14p21a503.coreapi.domain.ranking.service.RankingService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Slf4j
@Component
@RequiredArgsConstructor
public class RankingScheduler {

    private final RankingService rankingService;

    // 매일 자정(00:00:00)에 실행
    @Scheduled(cron = "0 0 0 * * *")
    public void scheduleDailyRanking() {
        log.info("정기 일간 랭킹 스냅샷 생성 스케줄러 실행");
        try {
            rankingService.createDailySnapshot();
        } catch (Exception e) {
            log.error("일간 랭킹 스냅샷 생성 중 오류 발생: {}", e.getMessage(), e);
        }
    }
}
