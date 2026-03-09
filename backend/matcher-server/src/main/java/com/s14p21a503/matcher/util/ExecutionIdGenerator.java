package com.s14p21a503.matcher.util;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.concurrent.atomic.AtomicLong;

@Component
public class ExecutionIdGenerator {
    /**
     * 결정론적 ExecutionId 생성.
     * [seqNo(54)][fillIndex(10)] 조합 (64비트)
     * 하나의 CMD당 최대 1024개의 체결 건수 수용 가능.
     */
    public long generate(long seqNo, int fillIndex) {
        if (fillIndex < 0 || fillIndex > 1023) {
            throw new IllegalArgumentException("fillIndex 값은 0에서 1023 사이여야 합니다.");
        }
        return (seqNo << 10) | fillIndex;
    }
}
