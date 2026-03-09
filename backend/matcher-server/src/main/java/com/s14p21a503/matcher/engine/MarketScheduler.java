package com.s14p21a503.matcher.engine;

import com.s14p21a503.matcher.dto.MarketControlEvent;
import com.s14p21a503.matcher.dto.MarketControlEvent.ControlType;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.ZonedDateTime;
import java.util.Set;

/**
 * 정규장 시간 관리 스케줄러.
 * 한국 시간 기준 09:00에 장을 열고, 15:30에 장을 닫으며 미체결 주문을 일괄 취소합니다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class MarketScheduler {

    private final MarketStateManager marketStateManager;
    private final PendingOrderManagerHolder orderManagerHolder;
    private final MessageQueueManager queueManager;
    private final MatcherConsumer matcherConsumer;
    private final HolidayManager holidayManager;

    /**
     * 평일 오전 09:00: 장 개시
     */
    @Scheduled(cron = "0 0 9 * * MON-FRI", zone = "Asia/Seoul")
    public void openMarket() {
        ZonedDateTime now = ZonedDateTime.now(java.time.ZoneId.of("Asia/Seoul"));
        if (holidayManager.isHoliday(now.toLocalDate())) {
            log.info("오늘은 휴장일이므로 장을 개시하지 않습니다. - Date: {}", now.toLocalDate());
            return;
        }
        
        log.info("정규장 개시 스케줄러 동작 시작 (09:00 KST)");
        marketStateManager.setStatus(MarketStatus.OPEN);
    }

    /**
     * 평일 오후 15:30: 장 종료 및 미체결 주문 일괄 취소
     */
    @Scheduled(cron = "0 30 15 * * MON-FRI", zone = "Asia/Seoul")
    public void closeMarket() {
        log.info("정규장 종료 스케줄러 동작 시작 (15:30 KST)");
        marketStateManager.setStatus(MarketStatus.CLOSE);
        
        // 모든 종목에 장 종료 제어 이벤트를 발행하여 엔진에서 일괄 취소를 수행하게 함
        Set<String> tickers = orderManagerHolder.getTickers();
        long now = System.currentTimeMillis();
        
        for (String ticker : tickers) {
            MarketControlEvent event = MarketControlEvent.builder()
                    .type(ControlType.MARKET_CLOSE)
                    .ticker(ticker)
                    .timestamp(now)
                    .build();
            // seqNo를 -1로 주어 관리용 이벤트임을 표시
            queueManager.enqueue(ticker, -1, event); 
            matcherConsumer.ensureConsumerStarted(ticker);
        }
        
        log.info("모든 종목({})에 대해 장 종료(MARKET_CLOSE) 이벤트 전송 완료", tickers.size());
    }
}
