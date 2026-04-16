package com.s14p21a503.coreapi.domain.market.service;

import com.s14p21a503.coreapi.domain.market.entity.MarketStatus;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.time.*;

/**
 * 전역 시장 상태 관리자 (Core API용).
 * 이제 Redis를 사용하지 않고 자바 힙 메모리(volatile)에 상태를 관리합니다.
 * 서버 재시작 시 @PostConstruct를 통해 현재 시간에 따른 상태를 계산하여 초기화합니다.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class MarketStateManager {

    private static final ZoneId KST_ZONE = ZoneId.of("Asia/Seoul");
    private static final LocalTime OPEN_TIME = LocalTime.of(9, 0);
    private static final LocalTime CLOSE_TIME = LocalTime.of(15, 30);

    private final HolidayManager holidayManager;

    // 멀티스레드 환경에서의 가시성 보장을 위해 volatile 사용
    private volatile MarketStatus currentStatus;

    /**
     * 서버 시작 시 시장 상태를 초기화합니다.
     */
    @PostConstruct
    public void init() {
        ZonedDateTime nowKst = ZonedDateTime.now(KST_ZONE);
        if (isTimeInMarketHours(nowKst)) {
            this.currentStatus = MarketStatus.OPEN;
        } else {
            this.currentStatus = MarketStatus.CLOSED;
        }
        log.info("[MarketStateManager] 초기 시장 상태 설정 완료: {}", currentStatus);
    }

    /**
     * 현재 시장이 주문 가능한 상태(OPEN)인지 확인합니다.
     * 메모리에 저장된 currentStatus를 참조합니다.
     */
    public boolean isMarketOpen() {
        return currentStatus == MarketStatus.OPEN;
    }

    /**
     * 특정 시간이 정규장 시간 내에 있는지 확인합니다.
     */
    public boolean isTimeInMarketHours(ZonedDateTime dateTime) {
        DayOfWeek day = dateTime.getDayOfWeek();
        
        // 1. 주말 체크
        if (day == DayOfWeek.SATURDAY || day == DayOfWeek.SUNDAY) {
            return false;
        }

        // 2. 휴장일 체크
        if (holidayManager.isHoliday(dateTime.toLocalDate())) {
            return false;
        }

        // 3. 시간 범위 체크 (09:00 <= time < 15:30)
        LocalTime time = dateTime.toLocalTime();
        return !time.isBefore(OPEN_TIME) && time.isBefore(CLOSE_TIME);
    }

    /**
     * 시장 상태를 업데이트합니다. (Service/Scheduler에서 호출)
     */
    public void updateMarketStatus(MarketStatus status) {
        this.currentStatus = status;
        log.info("[MarketStateManager] 메모리 시장 상태 업데이트 완료: {}", status);
    }

    /**
     * 현재 시장 상태를 반환합니다.
     */
    public MarketStatus getCurrentStatus() {
        return currentStatus;
    }
}
