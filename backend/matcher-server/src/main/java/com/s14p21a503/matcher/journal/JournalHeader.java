package com.s14p21a503.matcher.journal;

import lombok.Builder;
import lombok.Getter;

/**
 * 저널 레코드의 고정 길이 헤더.
 * [seqNo(8)][type(1)][refSeq(8)][timestamp(8)][partition(4)][offset(8)][payloadSize(4)] -> 41 bytes
 */
@Getter
@Builder
public class JournalHeader {
    public static final int HEADER_SIZE = 8 + 1 + 8 + 8 + 4 + 8 + 4; // 41 bytes

    private final long seqNo;
    private final JournalType type;
    private final long refSeq;      // RES/COMMIT일 경우 참조하는 CMD의 seqNo
    private final long timestamp;
    private final int partition;    // Kafka 파티션 보관
    private final long offset;      // Kafka 오프셋 보관
    private final int payloadSize;
}
