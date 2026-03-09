package com.s14p21a503.coreapi.domain.market.scheduler;

import com.s14p21a503.coreapi.domain.market.service.HolidayManager;
import com.s14p21a503.coreapi.domain.market.service.MarketService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.time.ZoneId;

/**
 * 전역 시장 상태 관리 스케줄러.
 * 코어 서버에서 중앙 집중적으로 장 개시/종료 신호를 발행합니다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class GlobalMarketScheduler {

    private final MarketService marketService;
    private final HolidayManager holidayManager;

    /**
     * 평일 오전 09:00: 전역 장 개시 신호 발행
     */
    @Scheduled(cron = "0 0 9 * * MON-FRI", zone = "Asia/Seoul")
    public void openMarket() {
        LocalDate now = LocalDate.now(ZoneId.of("Asia/Seoul"));
        if (holidayManager.isHoliday(now)) {
            log.info("[Global Scheduler] 오늘은 휴장일이므로 개장 신호를 발행하지 않습니다. - Date: {}", now);
            return;
        }
        
        log.info("[Global Scheduler] 정규장 개시 신호 이벤트 발행 시작 (09:00 KST)");
        marketService.openMarket();
    }

    /**
     * 평일 오후 15:30: 전역 장 종료 신호 발행
     */
    @Scheduled(cron = "0 30 15 * * MON-FRI", zone = "Asia/Seoul")
    public void closeMarket() {
        log.info("[Global Scheduler] 정규장 종료 신호 이벤트 발행 시작 (15:30 KST)");
        marketService.closeMarket();
    }
}
