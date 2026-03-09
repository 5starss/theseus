package com.s14p21a503.matcher.journal;

import com.s14p21a503.matcher.engine.PendingOrderManager;
import com.s14p21a503.matcher.engine.PendingOrderManagerHolder;
import com.s14p21a503.matcher.util.OrderIdDeduplicator;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import java.io.*;
import java.nio.file.*;
import java.util.Comparator;
import java.util.List;
import java.util.Optional;
import java.util.stream.StreamSupport;

/**
 * 스냅샷 관리 서비스.
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class SnapshotService {

    private final PendingOrderManagerHolder orderManagerHolder;
    private final OrderIdDeduplicator orderIdDeduplicator;
    private final JournalService journalService;

    @Value("${matcher.journal.dir:./logs}")
    private String logDir;

    @Value("${matcher.snapshot.retention:3}")
    private int snapshotRetention;

    /**
     * 현재 시점의 엔진 상태를 스냅샷으로 저장.
     */
    public void saveSnapshot(String ticker, long lastSeqNo) {
        Path tickerDir = Paths.get(logDir, ticker);
        Path snapshotPath = tickerDir.resolve("snapshot_" + lastSeqNo + ".bin");

        try {
            if (!Files.exists(tickerDir)) {
                Files.createDirectories(tickerDir);
            }

            PendingOrderManager orderManager = orderManagerHolder.getManager(ticker);
            SnapshotState.SnapshotStateBuilder builder = SnapshotState.builder().lastSeqNo(lastSeqNo);
            
            // 상태 캡처
            orderManager.fillSnapshotBuilder(builder);
            builder.deduplicatorActionBuckets(orderIdDeduplicator.getActionBucketsCopy());

            SnapshotState state = builder.build();

            // 파일 안전하게 저장 (임시 파일에 쓰고 Rename)
            Path tempPath = tickerDir.resolve("snapshot_" + lastSeqNo + ".bin.tmp");
            try (ObjectOutputStream oos = new ObjectOutputStream(new FileOutputStream(tempPath.toFile()))) {
                oos.writeObject(state);
            }

            Files.move(tempPath, snapshotPath, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);

            log.info("[{}] 스냅샷 저장 완료: seqNo={}, 경로={}", ticker, lastSeqNo, snapshotPath);
            
            // 저널 로테이션 수행 (성공한 스냅샷 이후의 저널만 남기기 위해 파일 비움)
            journalService.rotateJournal(ticker);

            // 오래된 스냅샷 정리 (Optional)
            cleanupOldSnapshots(tickerDir, lastSeqNo);

        } catch (IOException e) {
            log.error("[{}] 스냅샷 저장 실패", ticker, e);
        }
    }

    /**
     * 가장 최근 스냅샷 로드.
     */
    public Optional<SnapshotState> loadLatestSnapshot(String ticker) {
        Path tickerDir = Paths.get(logDir, ticker);
        if (!Files.exists(tickerDir)) return Optional.empty();

        try (DirectoryStream<Path> stream = Files.newDirectoryStream(tickerDir, "snapshot_*.bin")) {
            return StreamSupport.stream(stream.spliterator(), false)
                    .max(Comparator.comparing(p -> {
                        String name = p.getFileName().toString();
                        return Long.parseLong(name.substring(9, name.length() - 4));
                    }))
                    .map(path -> {
                        try (ObjectInputStream ois = new ObjectInputStream(new FileInputStream(path.toFile()))) {
                            return (SnapshotState) ois.readObject();
                        } catch (Exception e) {
                            log.error("스냅샷 파일 읽기 실패: {}", path, e);
                            return null;
                        }
                    });
        } catch (IOException e) {
            log.error("[{}] 스냅샷 디렉토리 스캔 실패", ticker, e);
            return Optional.empty();
        }
    }

    /**
     * 지정된 개수 이상의 오래된 스냅샷 파일들을 삭제하여 디스크 공간을 관리합니다.
     */
    private void cleanupOldSnapshots(Path tickerDir, long currentSeqNo) {
        try (DirectoryStream<Path> stream = Files.newDirectoryStream(tickerDir, "snapshot_*.bin")) {
            // 파일을 seqNo 역순(최신순)으로 정렬
            List<Path> snapshots = StreamSupport.stream(stream.spliterator(), false)
                    .sorted((p1, p2) -> {
                        long s1 = extractSeqNo(p1);
                        long s2 = extractSeqNo(p2);
                        return Long.compare(s2, s1); // 내림차순 (최신 것이 위로)
                    })
                    .toList();

            // 설정된 개수만큼 남기고 나머지는 삭제
            if (snapshots.size() > snapshotRetention) {
                for (int i = snapshotRetention; i < snapshots.size(); i++) {
                    Files.deleteIfExists(snapshots.get(i));
                    log.info("[{}] 오래된 스냅샷 삭제됨: {}", tickerDir.getFileName(), snapshots.get(i).getFileName());
                }
            }
        } catch (IOException e) {
            log.warn("[{}] 오래된 스냅샷 정리 중 오류 발생", tickerDir.getFileName(), e);
        }
    }

    private long extractSeqNo(Path path) {
        String name = path.getFileName().toString();
        try {
            // snapshot_100.bin -> 100 추출
            return Long.parseLong(name.substring(9, name.length() - 4));
        } catch (Exception e) {
            return 0L;
        }
    }
}
