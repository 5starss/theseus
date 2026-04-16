package com.s14p21a503.coreapi.domain.order.entity;

public enum OrderStatus {
    OPEN, //주문 접수
    PARTIAL, //부분 체결
    FILLED, //전부 체결
    PENDING_CANCEL, //취소 대기
    CANCELLED //주문 취소
}
