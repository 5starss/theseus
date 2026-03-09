package com.s14p21a503.matcher.journal;

import lombok.Getter;
import lombok.RequiredArgsConstructor;

/**
 * 저널 레코드의 타입을 정의하는 Enum.
 */
@Getter
@RequiredArgsConstructor
public enum JournalType {
    /**
     * 입력 명령 (주문 신규/취소, 틱 수신 등)
     */
    CMD((byte) 1),

    /**
     * 매칭 엔진의 중간 처리 결과
     */
    RES((byte) 2),

    /**
     * 파이프라인(엔진+로깅+전송) 전체 완료 마커
     */
    COMMIT((byte) 3),

    /**
     * 오더북 상태 스냅샷
     */
    SNAPSHOT((byte) 4),

    /**
     * 저널 파일 비우기 명령 (내부 제어용)
     */
    TRUNCATE((byte) 99);

    private final byte code;

    public static JournalType fromCode(byte code) {
        for (JournalType type : values()) {
            if (type.code == code) {
                return type;
            }
        }
        throw new IllegalArgumentException("Unknown JournalType code: " + code);
    }
}
