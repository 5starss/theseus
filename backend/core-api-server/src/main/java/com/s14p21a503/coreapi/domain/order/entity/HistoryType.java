package com.s14p21a503.coreapi.domain.order.entity;

public enum HistoryType {
    EXECUTION,          // 체결
    CANCELLATION,       // 정상 취소
    SYSTEM_CANCELLATION // 시스템 오류로 인한 취소
}
