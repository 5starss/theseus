package com.s14p21a503.matcher.engine;

/**
 * 시장의 상태를 정의하는 Enum.
 */
public enum MarketStatus {
    OPEN,  // 정규장 운영 시간 (09:00 ~ 15:30)
    CLOSE, // 그 외 시간 (종료 시 미체결 주문 일괄 취소)
    HALT   // 일시 정지 (운영 시간 중 관리자에 의해 일시적으로 거래가 중단된 상태)
}
