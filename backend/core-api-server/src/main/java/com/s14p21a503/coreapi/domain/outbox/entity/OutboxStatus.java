package com.s14p21a503.coreapi.domain.outbox.entity;

public enum OutboxStatus {
    INIT,        // 대기중
    PUBLISHED,   // 전송완료
    FAILED       // 전송실패 (재시도 초과 등)
}
