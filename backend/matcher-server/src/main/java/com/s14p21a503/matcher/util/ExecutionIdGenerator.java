package com.s14p21a503.matcher.util;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import java.util.concurrent.atomic.AtomicLong;

@Component
public class ExecutionIdGenerator {
    /**
     * 전역적으로 고유한 ExecutionId 생성.
     * [Version(1)][Partition(5)][Offset(40)][fillIndex(16)] 조합 (62비트)
     * - Version: 1 (기존 seqNo 기반 ID와의 충돌 방지를 위한 접두어)
     * - Partition: 최대 32개 지원 (5비트)
     * - Offset: 최대 1조 개의 메시지 지원 (40비트)
     * - fillIndex: CMD 하나당 최대 65,536개의 체결/취소 지원 (16비트)
     * 총 62비트를 사용하여 양수 범위(Long.MAX_VALUE) 내에서 안전하게 생성합니다.
     */
    public long generate(int partition, long offset, int fillIndex) {
        if (fillIndex < 0 || fillIndex > 65_535) {
            throw new IllegalArgumentException("fillIndex 값은 0에서 65,535 사이여야 합니다.");
        }
        
        long version = 1L; // 신규 ID 체계 식별자
        long pField = Math.max(0, (long) partition) & 0x1FL; // 5 bits (0~31)
        long oField = offset & 0xFFFFFFFFFFL;               // 40 bits (max 1 Trillion)
        long fField = (long) fillIndex & 0xFFFFL;           // 16 bits (0~65535)

        // [비트 구성] | 0 (1bit) | 1 (Version 1bit) | Partition (5bit) | Offset (40bit) | fillIndex (16bit) |
        return (version << 61) | (pField << 56) | (oField << 16) | fField;
    }
}
