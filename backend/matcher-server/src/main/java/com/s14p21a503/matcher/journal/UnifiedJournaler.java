package com.s14p21a503.matcher.journal;

import lombok.extern.slf4j.Slf4j;

import java.io.IOException;
import java.io.RandomAccessFile;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;
import java.util.ArrayList;
import java.util.List;

/**
 * 종목별 단일 저널링 엔진.
 * 고성능 바이너리 Appender 및 복구용 리더 기능 포함.
 */
@Slf4j
public class UnifiedJournaler implements AutoCloseable {
    private final String ticker;
    private final String logDir;
    private final FileChannel channel;
    private final AtomicLong currentSeqNo = new AtomicLong(0);
    
    private final BlockingQueue<JournalRecord> writeQueue = new LinkedBlockingQueue<>(10000);
    private final Thread writerThread;
    private final AtomicBoolean running = new AtomicBoolean(true);

    /**
     * 특정 종목의 저널러를 초기화합니다.
     * 기존 로그 파일이 있다면 마지막 시퀀스를 읽어와 이어 쓰기를 준비하고, 
     * 비동기 기록을 위한 백그라운드 스레드를 시작합니다.
     * 
     * @param ticker 종목 코드
     * @param logDir 로그 저장 기본 디렉토리
     * @throws IOException 파일 액세스 실패 시 발생
     */
    public UnifiedJournaler(String ticker, String logDir) throws IOException {
        this.ticker = ticker;
        this.logDir = logDir;
        
        Path dirPath = Paths.get(logDir, ticker);
        if (!Files.exists(dirPath)) {
            Files.createDirectories(dirPath);
        }

        Path logPath = dirPath.resolve("journal.log");
        @SuppressWarnings("resource")
        RandomAccessFile raf = new RandomAccessFile(logPath.toFile(), "rw");
        this.channel = raf.getChannel();
        
        // 파일의 끝으로 포인터 이동 (Append 모드)
        this.channel.position(this.channel.size());
        
        // 마지막 시퀀스 번호 초기화
        initializeSeqNo(ticker, logPath);
        
        log.info("[{}] 저널러 초기화 완료 (Seq: {}): {}", ticker, currentSeqNo.get(), logPath);

        this.writerThread = new Thread(this::writerLoop, "JournalWriter-" + ticker);
        this.writerThread.setDaemon(true);
        this.writerThread.start();
    }

    /**
     * 기존 저널 파일을 스캔하여 마지막 시퀀스 번호를 찾아 currentSeqNo를 초기화합니다.
     */
    private void initializeSeqNo(String ticker, Path logPath) {
        try (JournalReader reader = new JournalReader(ticker, logPath)) {
            JournalReader.JournalEntry entry;
            long lastSeq = 0;
            while ((entry = reader.readNext()) != null) {
                lastSeq = entry.getHeader().getSeqNo();
            }
            this.currentSeqNo.set(lastSeq);
        } catch (IOException e) {
            log.warn("[{}] 기존 저널 시퀀스 초기화 실패 (신규 파일로 간주): {}", ticker, e.getMessage());
            this.currentSeqNo.set(0);
        }
    }

    /**
     * 저널 기록 요청의 상태를 추적하는 결과 객체.
     * 시퀀스 번호가 할당된 시점(Assigned)과 디스크에 물리적으로 기록된 시점(Flushed)에 대한 콜백을 제공합니다.
     */
    public static class JournalOutcome {
        private final CompletableFuture<Long> assignedFuture = new CompletableFuture<>();
        private final CompletableFuture<Long> flushedFuture = new CompletableFuture<>();

        /** 시퀀스 번호가 할당되면 완료됩니다. (엔진 처리 시작 가능) */
        public CompletableFuture<Long> whenAssigned() { return assignedFuture; }
        /** 디스크 플러시까지 완료되면 완료됩니다. (Kafka Ack 가능) */
        public CompletableFuture<Long> whenFlushed() { return flushedFuture; }
    }

    /**
     * 저널 레코드를 비동기 기록 큐에 추가하고, 완료 상태를 추적하는 Outcome 객체를 반환합니다.
     * 
     * @param type 저널 타입 (CMD, RES, COMMIT 등)
     * @param refSeq 참조하는 시퀀스 번호 (CMD의 경우 0, RES/COMMIT은 해당 CMD 번호)
     * @param partition 카프카 파티션 (CMD인 경우 유효, 나머지는 -1)
     * @param offset 카프카 오프셋 (CMD인 경우 유효, 나머지는 -1)
     * @param payload 실제 데이터 바이트 배열
     * @return 시퀀스 할당 및 플러시 시점을 추적할 수 있는 JournalOutcome
     * @throws IOException 큐 대기 중 인터럽트 발생 시
     */
    public JournalOutcome write(JournalType type, long refSeq, int partition, long offset, byte[] payload) throws IOException {
        JournalOutcome outcome = new JournalOutcome();
        long timestamp = System.currentTimeMillis();
        
        JournalRecord record = new JournalRecord(0, type, refSeq, timestamp, partition, offset, payload, outcome);
        try {
            if (!writeQueue.offer(record, 1, TimeUnit.SECONDS)) {
                log.error("[{}] 저널 쓰기 큐 포화! (Type: {})", ticker, type);
                outcome.assignedFuture.completeExceptionally(new IOException("Journal queue is full"));
                outcome.flushedFuture.completeExceptionally(new IOException("Journal queue is full"));
            }
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            outcome.assignedFuture.completeExceptionally(e);
            outcome.flushedFuture.completeExceptionally(e);
            throw new IOException("저널 기록 중 인터럽트 발생", e);
        }

        return outcome;
    }

    /**
     * 기존 하위 호환성을 위한 편의 메서드.
     */
    public JournalOutcome write(JournalType type, long refSeq, byte[] payload) throws IOException {
        return write(type, refSeq, -1, -1L, payload);
    }

    /**
     * 백그라운드에서 큐의 데이터를 꺼내 시퀀스를 할당하고 배치 쓰기를 수행하는 루프입니다.
     */
    private void writerLoop() {
        List<JournalRecord> batch = new ArrayList<>(100);
        while (running.get() || !writeQueue.isEmpty()) {
            try {
                // 최대 100ms 만큼 기다림
                JournalRecord first = writeQueue.poll(100, TimeUnit.MILLISECONDS);
                if (first != null) {
                        batch.add(first);
                        writeQueue.drainTo(batch, 99); // 최대 100개를 배치로 한 번에 이동
                        
                        List<JournalRecord> writeBatchList = new ArrayList<>();
                        
                        for (JournalRecord r : batch) {
                            if (r.type == JournalType.TRUNCATE) {
                                // 1. TRUNCATE 이전에 쌓인 데이터가 있다면 먼저 씀
                                if (!writeBatchList.isEmpty()) {
                                    flushBatch(writeBatchList);
                                    writeBatchList.clear();
                                }
                                
                                // 2. 파일 비우기 직접 수행 (Writer 스레드이므로 락 불필요)
                                try {
                                    channel.truncate(0);
                                    channel.position(0);
                                    log.info("[{}] 저널 파일이 이벤트를 통해 비워졌습니다. (시퀀스 유지: {})", ticker, currentSeqNo.get());
                                    r.outcome.flushedFuture.complete(currentSeqNo.get());
                                    r.outcome.assignedFuture.complete(currentSeqNo.get());
                                } catch (IOException e) {
                                    log.error("[{}] Truncate 처리 중 오류", ticker, e);
                                    r.outcome.flushedFuture.completeExceptionally(e);
                                    r.outcome.assignedFuture.completeExceptionally(e);
                                }
                            } else {
                                // 일반 레코드는 시퀀스 할당 후 배기 리스트에 추가
                                r.seq = currentSeqNo.incrementAndGet();
                                r.outcome.assignedFuture.complete(r.seq);
                                writeBatchList.add(r);
                            }
                        }

                        // 3. 남은 일반 레코드들 마저 쓰기
                        if (!writeBatchList.isEmpty()) {
                            flushBatch(writeBatchList);
                        }
                    
                    batch.clear();
                }
            } catch (Exception e) {
                log.error("[{}] 저널 배치 쓰기 중 심각한 오류", ticker, e);
                for (JournalRecord r : batch) {
                    r.outcome.assignedFuture.completeExceptionally(e);
                    r.outcome.flushedFuture.completeExceptionally(e);
                }
                batch.clear();
            }
        }
    }

    /**
     * 레코드 리스트를 하나의 바이너리 블록으로 묶어 물리 파일에 기록합니다.
     */
    private void writeBatch(List<JournalRecord> batch) throws IOException {
        int totalSize = 0;
        for (JournalRecord r : batch) {
            totalSize += JournalHeader.HEADER_SIZE + (r.payload != null ? r.payload.length : 0) + 4;
        }

        // [최적화] Heap 메모리가 아닌 Direct Buffer를 사용하여 커널로의 복사 비용(Zero-copy)을 줄입니다.
        ByteBuffer fullBuf = ByteBuffer.allocateDirect(totalSize);
        
        for (JournalRecord r : batch) {
            int pSize = (r.payload != null) ? r.payload.length : 0;
            int headerStart = fullBuf.position();
            
            // [최적화] 별도의 헤더용 Buffer 할당 없이 직접 메인 Buffer에 기록 (GC Pressure 제거)
            fullBuf.putLong(r.seq);
            fullBuf.put(r.type.getCode());
            fullBuf.putLong(r.refSeq);
            fullBuf.putLong(r.timestamp);
            fullBuf.putInt(r.partition);
            fullBuf.putLong(r.offset);
            fullBuf.putInt(pSize);
            
            // 헤더 정보만 사용하여 체크섬 계산 (복사 없이 ByteBuffer 직접 참조)
            long checksum = JournalChecksum.calculate(fullBuf, headerStart, JournalHeader.HEADER_SIZE, r.payload);
            
            if (r.payload != null) {
                fullBuf.put(r.payload);
            }
            fullBuf.putInt((int) checksum);
        }
        fullBuf.flip();

        while (fullBuf.hasRemaining()) {
            channel.write(fullBuf);
        }
    }

    /**
     * 레코드 배치를 파일에 쓰고 물리적으로 플러시합니다.
     */
    private void flushBatch(List<JournalRecord> batch) throws IOException {
        writeBatch(batch);
        channel.force(false);
        for (JournalRecord r : batch) {
            r.outcome.flushedFuture.complete(r.seq);
        }
    }

    /**
     * 현재 파일 채널의 데이터를 OS 디스크 버퍼로 물리적 Flush를 강제합니다.
     */
    public void force() throws IOException {
        channel.force(false);
    }

    /**
     * 저널 파일을 비우고 시퀀스를 유지합니다. (로테이션용)
     * 이제 명령을 큐에 넣어 Writer 스레드에서 안전하고 비차단적으로 처리합니다.
     */
    public JournalOutcome truncateJournal() throws IOException {
        log.info("[{}] 저널 비우기(Truncate) 요청이 접수되었습니다.", ticker);
        return write(JournalType.TRUNCATE, 0, null);
    }

    /**
     * 저널러를 안전하게 종료합니다. 
     * 백그라운드 스레드를 중지하고 남은 데이터를 Flush한 뒤 채널을 닫습니다.
     */
    @Override
    public void close() throws IOException {
        running.set(false);
        try {
            writerThread.join(2000);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        if (channel != null && channel.isOpen()) {
            channel.force(true);
            channel.close();
        }
    }

    /**
     * 저널 기록 요청을 담는 내부 레코드 클래스
     */
    private static class JournalRecord {
        long seq;
        final JournalType type;
        final long refSeq;
        final long timestamp;
        final int partition;
        final long offset;
        final byte[] payload;
        final JournalOutcome outcome;

        JournalRecord(long seq, JournalType type, long refSeq, long timestamp, int partition, long offset, byte[] payload, JournalOutcome outcome) {
            this.seq = seq;
            this.type = type;
            this.refSeq = refSeq;
            this.timestamp = timestamp;
            this.partition = partition;
            this.offset = offset;
            this.payload = payload;
            this.outcome = outcome;
        }
    }
}
