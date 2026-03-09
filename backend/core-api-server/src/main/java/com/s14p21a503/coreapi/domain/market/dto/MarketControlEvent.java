package com.s14p21a503.coreapi.domain.market.dto;

import lombok.*;

import java.io.Serializable;
import java.util.List;

/**
 * 시스템 관리용 이벤트 DTO.
 * 매칭 엔진의 상태를 전역적으로 제어할 때 사용합니다.
 */
@Getter
@NoArgsConstructor
@AllArgsConstructor
@Builder
@ToString
public class MarketControlEvent implements Serializable {
    private static final long serialVersionUID = 1L;

    public enum ControlType {
        MARKET_OPEN,    // 스케줄에 따른 정상 개장
        MARKET_CLOSE,   // 스케줄에 따른 정상 종료
        MARKET_HALT,    // 관리자에 의한 일시 정지 (Halt)
        MARKET_RESUME,  // 일시 정지 해제 및 재개
        SET_HOLIDAYS    // 휴장일 리스트 명시적 업데이트
    }

    private ControlType type;
    private String ticker; // 특정 종목 제어 시 사용 (null이면 전 종목)
    private long timestamp;
    private List<String> holidayDates; // ISO-8601 (yyyy-MM-dd) 형식의 날짜 리스트
}
