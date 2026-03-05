package com.s14p21a503.matcher.util;

import java.util.concurrent.atomic.AtomicLong;

public class ExecutionIdGenerator {
    // 2024-01-01 00:00:00 UTC 기준
    private static final long EPOCH = 1704067200000L;
    private static final AtomicLong sequence = new AtomicLong(0L);

    public static long generate() {
        long currentMillis = System.currentTimeMillis();
        // 동일한 밀리초 내에서도 sequence는 증가하며 고유성을 보장.
        // 최대 16비트 (0 ~ 65535) 공간만 사용하도록 마스킹 처리.
        long seq = sequence.getAndIncrement() & 0xFFFF; 
        
        return ((currentMillis - EPOCH) << 16) | seq;
    }
}
