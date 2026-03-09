package com.s14p21a503.matcher.journal;

import java.nio.ByteBuffer;
import java.util.zip.CRC32;

/**
 * 저널 레코드의 무결성 검증을 위한 체크섬 유틸리티.
 */
public class JournalChecksum {
    public static long calculate(byte[] header, byte[] payload) {
        CRC32 crc = new CRC32();
        crc.update(header);
        if (payload != null) {
            crc.update(payload);
        }
        return crc.getValue();
    }

    /**
     * ByteBuffer를 직접 사용하여 추가 복사 없이 체크섬을 계산합니다.
     */
    public static long calculate(java.nio.ByteBuffer headerBuf, int headerOffset, int headerLen, byte[] payload) {
        CRC32 crc = new CRC32();
        
        // 원본 버퍼 상태 보존을 위한 듀플리케이트 사용
        ByteBuffer temp = headerBuf.duplicate();
        temp.position(headerOffset);
        temp.limit(headerOffset + headerLen);
        
        crc.update(temp);
        
        if (payload != null) {
            crc.update(payload);
        }
        return crc.getValue();
    }
}
