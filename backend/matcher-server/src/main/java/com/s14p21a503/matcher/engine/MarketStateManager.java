package com.s14p21a503.matcher.engine;

import lombok.Getter;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.time.DayOfWeek;
import java.time.Instant;
import java.time.LocalTime;
import java.time.ZonedDateTime;
import java.time.ZoneId;

/**
 * 시장 상태 관리자 (OPEN/CLOSE).
 * 한국 표준시(KST)를 기준으로 정규장 운영 여부를 관리합니다.
 */
@Slf4j
@Component
public class MarketStateManager {

    private static final ZoneId KST_ZONE = ZoneId.of("Asia/Seoul");
    private static final LocalTime OPEN_TIME = LocalTime.of(9, 0);
    private static final LocalTime CLOSE_TIME = LocalTime.of(15, 30);

    private final HolidayManager holidayManager;

    @Getter
    private volatile MarketStatus status;

    // 성능 최적화를 위한 캐시 필드 (Thread-safe 가시성을 위해 volatile 사용)
    private volatile long cachedOpenMillis = -1;
    private volatile long cachedCloseMillis = -1;
    private volatile int cachedDayOfYear = -1;

    public MarketStateManager(HolidayManager holidayManager) {
        this.holidayManager = holidayManager;
        updateStatusByCurrentTime();
    }

    /**
     * 현재 시간이 정규장 시간(평일 09:00 ~ 15:30) 내에 있는지 확인합니다.
     */
    public boolean isTimeInMarketHours(long timestamp) {
        // 1. Fast-path: 캐싱된 오늘 범위 내에 있는지 먼저 확인
        long open = cachedOpenMillis;
        long close = cachedCloseMillis;
        
        if (timestamp >= open && timestamp < close) {
            return true;
        }

        // 2. Slow-path: 캐시 범위를 벗어난 경우 (장외 시간, 날짜 변경, 과거 데이터 등) 정밀 체크
        return slowCheckAndTimeUpdate(timestamp);
    }

    /**
     * 객체 생성을 수반하는 정밀 체크 및 필요 시 캐시 갱신
     */
    private synchronized boolean slowCheckAndTimeUpdate(long timestamp) {
        ZonedDateTime dateTime = ZonedDateTime.ofInstant(
                Instant.ofEpochMilli(timestamp), KST_ZONE);
        
        // 날짜가 바뀌었거나 캐시가 비어있으면 해당 날짜 기준으로 캐시 갱신 시도
        int dayOfYear = dateTime.getDayOfYear();
        if (dayOfYear != cachedDayOfYear) {
            refreshCacheForDate(dateTime);
        }

        // 갱신된 캐시 기준으로 다시 한 번 체크
        return timestamp >= cachedOpenMillis && timestamp < cachedCloseMillis;
    }

    /**
     * 특정 날짜 기준의 장 시작/종료 밀리초 범위를 계산하여 캐싱
     */
    private void refreshCacheForDate(ZonedDateTime dateTime) {
        DayOfWeek day = dateTime.getDayOfWeek();
        boolean isWeekend = (day == DayOfWeek.SATURDAY || day == DayOfWeek.SUNDAY);
        boolean isHoliday = holidayManager.isHoliday(dateTime.toLocalDate());
        
        if (isWeekend || isHoliday) {
            // 주말이거나 휴장일이면 절대 열리지 않도록 범위를 불가능한 값으로 설정
            cachedOpenMillis = Long.MAX_VALUE;
            cachedCloseMillis = Long.MIN_VALUE;
            log.info("시장 시간 캐시 갱신 (휴장/주말) - Date: {}, Weekend: {}, Holiday: {}", 
                    dateTime.toLocalDate(), isWeekend, isHoliday);
        } else {
            // 평일이면 해당 날짜의 09:00 ~ 15:30 계산
            ZonedDateTime openAt = dateTime.with(OPEN_TIME).withSecond(0).withNano(0);
            ZonedDateTime closeAt = dateTime.with(CLOSE_TIME).withSecond(0).withNano(0);
            cachedOpenMillis = openAt.toInstant().toEpochMilli();
            cachedCloseMillis = closeAt.toInstant().toEpochMilli();
        }
        cachedDayOfYear = dateTime.getDayOfYear();
        log.debug("시장 시간 캐시 갱신 - Date: {}, Range: {} ~ {}", 
                dateTime.toLocalDate(), cachedOpenMillis, cachedCloseMillis);
    }

    public boolean isMarketOpen() {
        return this.status == MarketStatus.OPEN;
    }

    public synchronized void setStatus(MarketStatus newStatus) {
        if (this.status != newStatus) {
            log.info("시장 상태 변경: {} -> {}", this.status, newStatus);
            this.status = newStatus;
        }
    }

    /**
     * 현재 KST 서버 시간 기준으로 상태를 강제 업데이트합니다.
     */
    public void updateStatusByCurrentTime() {
        ZonedDateTime nowKst = ZonedDateTime.now(KST_ZONE);
        
        // 캐시 강제 갱신을 위해 날짜 체크 로직 포함
        if (nowKst.getDayOfYear() != cachedDayOfYear) {
            synchronized (this) {
                refreshCacheForDate(nowKst);
            }
        }

        if (isTimeInMarketHours(nowKst.toInstant().toEpochMilli())) {
            setStatus(MarketStatus.OPEN);
        } else {
            setStatus(MarketStatus.CLOSE);
        }
    }
}
