package com.s14p21a503.coreapi.domain.market.entity;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

/**
 * 전역 시장 상태 정의
 */
@Getter
@RequiredArgsConstructor
public enum MarketStatus {
    OPEN("OPEN", "장 중 (주문 가능)"),
    CLOSED("CLOSED", "장 종료 (주문 불가)"),
    HALTED("HALTED", "일시 정지 (주문 불가)");

    private final String code;
    private final String description;

    public static MarketStatus of(String code) {
        for (MarketStatus status : values()) {
            if (status.code.equalsIgnoreCase(code)) {
                return status;
            }
        }
        return CLOSED; // 기본값
    }
}
