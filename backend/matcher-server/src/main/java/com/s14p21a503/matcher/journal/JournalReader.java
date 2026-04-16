package com.s14p21a503.matcher.journal;

import lombok.extern.slf4j.Slf4j;

import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Path;

/**
 * 저널 파일 리더.
 * 체크섬 검증 및 Partial Write 감지 기능 포함.
 */
@Slf4j
public class JournalReader implements AutoCloseable {
    private final FileChannel channel;
    private final String ticker;

    public JournalReader(String ticker, Path logPath) throws IOException {
        this.ticker = ticker;
        @SuppressWarnings("resource")
        RandomAccessFile raf = new RandomAccessFile(logPath.toFile(), "r");
        this.channel = raf.getChannel();
    }

    public JournalEntry readNext() throws IOException {
        if (channel.position() >= channel.size()) {
            return null;
        }

        long startPosition = channel.position();
        
        // 1. Header 읽기
        ByteBuffer headerBuf = ByteBuffer.allocate(JournalHeader.HEADER_SIZE);
        if (channel.read(headerBuf) < JournalHeader.HEADER_SIZE) {
            log.warn("[{}] 헤더 일부가 누락됨 (위치: {}). 해당 지점 이후 절단.", ticker, startPosition);
            return null;
        }
        headerBuf.flip();

        byte[] headerBytes = new byte[JournalHeader.HEADER_SIZE];
        headerBuf.get(headerBytes);
        headerBuf.rewind();

        long seqNo = headerBuf.getLong();
        byte typeCode = headerBuf.get();
        long refSeq = headerBuf.getLong();
        long timestamp = headerBuf.getLong();
        int partition = headerBuf.getInt();
        long offset = headerBuf.getLong();
        int payloadSize = headerBuf.getInt();

        // 2. Payload 읽기
        byte[] payloadBytes = null;
        if (payloadSize > 0) {
            ByteBuffer payloadBuf = ByteBuffer.allocate(payloadSize);
            if (channel.read(payloadBuf) < payloadSize) {
                log.warn("[{}] 페이로드 일부가 누락됨 (Seq: {}). 해당 지점 이후 절단.", ticker, seqNo);
                return null;
            }
            payloadBytes = payloadBuf.array();
        }

        // 3. Checksum 읽기
        ByteBuffer checksumBuf = ByteBuffer.allocate(4);
        if (channel.read(checksumBuf) < 4) {
            log.warn("[{}] 체크섬 누락 (Seq: {}). 해당 지점 이후 절단.", ticker, seqNo);
            return null;
        }
        checksumBuf.flip();
        int savedChecksum = checksumBuf.getInt();

        // 4. 무결성 검증
        long calculatedChecksum = JournalChecksum.calculate(headerBytes, payloadBytes);
        if ((int) calculatedChecksum != savedChecksum) {
            log.error("[{}] 체크섬 불일치 (Seq: {}). 데이터 오염 발생!", ticker, seqNo);
            return null;
        }

        JournalHeader header = JournalHeader.builder()
                .seqNo(seqNo)
                .type(JournalType.fromCode(typeCode))
                .refSeq(refSeq)
                .timestamp(timestamp)
                .partition(partition)
                .offset(offset)
                .payloadSize(payloadSize)
                .build();

        return new JournalEntry(header, payloadBytes);
    }

    @Override
    public void close() throws IOException {
        if (channel != null) channel.close();
    }

    @lombok.Value
    public static class JournalEntry {
        JournalHeader header;
        byte[] payload;
    }
}
