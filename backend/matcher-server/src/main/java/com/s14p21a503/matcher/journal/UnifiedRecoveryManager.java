package com.s14p21a503.matcher.journal;

import com.s14p21a503.matcher.dto.*;
import com.s14p21a503.matcher.engine.PendingOrderManager;
import com.s14p21a503.matcher.engine.PendingOrderManagerHolder;
import com.s14p21a503.matcher.engine.MarketStateManager;
import com.s14p21a503.matcher.util.OrderIdDeduplicator;
import com.s14p21a503.matcher.util.KafkaIdempotencyManager;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import jakarta.annotation.PostConstruct;
import java.io.IOException;
import java.nio.file.*;
import java.util.*;

/**
 * 저널 기반 상태 복구 매니저.
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class UnifiedRecoveryManager {

    private final PendingOrderManagerHolder orderManagerHolder;
    private final OrderIdDeduplicator orderIdDeduplicator;
    private final KafkaIdempotencyManager kafkaIdempotencyManager;
    private final JournalService journalService;
    private final SnapshotService snapshotService;
    private final MarketStateManager marketStateManager;

    @Value("${matcher.journal.dir:./logs}")
    private String logDir;


    /**
     * 시스템 시작 시 실행되는 복구 프로세스의 입구입니다.
     * 저널 디렉토리를 스캔하여 각 종목(Ticker)별로 복구 로직을 트리거합니다.
     */
    @PostConstruct
    public void recover() {
        log.info("통합 복구 프로세스 시작 중...");
        kafkaIdempotencyManager.clear();
        
        try (DirectoryStream<Path> stream = Files.newDirectoryStream(Paths.get(logDir))) {
            for (Path tickerDir : stream) {
                if (Files.isDirectory(tickerDir)) {
                    String ticker = tickerDir.getFileName().toString();
                    recoverTicker(ticker, tickerDir.resolve("journal.log"));
                }
            }
        } catch (IOException e) {
            log.error("디렉토리 스캔 중 복구 실패", e);
        }
        
        log.info("통합 복구 프로세스 완료.");
    }

    /**
     * 특정 종목(Ticker)의 데이터를 복구합니다.
     * 1. 최신 스냅샷을 로드하여 베이스 상태를 구축합니다.
     * 2. 스냅샷 이후의 저널 로그를 스캔하여 명령(CMD), 결과(RES), 커밋(COMMIT) 정보를 수집합니다.
     * 3. 수집된 정보를 바탕으로 과거의 상태를 순차적으로 재현(Replay)합니다.
     * 
     * @param ticker 복구할 종목 코드
     * @param logPath 해당 종목의 저널 로그 파일 경로
     */
    void recoverTicker(String ticker, Path logPath) {
        log.info("[{}] 저널 복구 시작 (경로: {})", ticker, logPath);
        
        PendingOrderManager orderManager = orderManagerHolder.getManager(ticker);
        long startSeqNo = 0;

        // 1. 최신 스냅샷 로드
        Optional<SnapshotState> snapshotOpt = snapshotService.loadLatestSnapshot(ticker);
        if (snapshotOpt.isPresent()) {
            SnapshotState snapshot = snapshotOpt.get();
            orderManager.restoreState(snapshot);
            orderIdDeduplicator.restoreState(snapshot.getDeduplicatorActionBuckets());
            startSeqNo = snapshot.getLastSeqNo();
            // [TODO] 스냅샷에도 Kafka Offset 정보가 있다면 복원 필요
            log.info("[{}] 스냅샷 복원 완료. (SeqNo: {})", ticker, startSeqNo);
        }

        if (!Files.exists(logPath)) return;

        Map<Long, JournalReader.JournalEntry> cmdMap = new LinkedHashMap<>();
        Map<Long, List<ExecutionResult>> resMap = new HashMap<>();
        Set<Long> committedSeqs = new HashSet<>();

        // [Pass 1] 저널 전체 스캔: CMD, RES, COMMIT 수집
        try (JournalReader reader = new JournalReader(ticker, logPath)) {
            JournalReader.JournalEntry entry;
            while ((entry = reader.readNext()) != null) {
                JournalHeader header = entry.getHeader();
                
                // 오프셋 정보 업데이트 (중복 방지 필터 초기화용)
                if (header.getType() == JournalType.CMD) {
                    kafkaIdempotencyManager.updateLastOffset(ticker, header.getPartition(), header.getOffset());
                }

                if (header.getSeqNo() <= startSeqNo) continue;

                switch (header.getType()) {
                    case CMD:
                        cmdMap.put(header.getSeqNo(), entry);
                        break;
                    case RES:
                        ExecutionResult res = (ExecutionResult) JournalSerializer.deserialize(entry.getPayload());
                        resMap.computeIfAbsent(header.getRefSeq(), k -> new ArrayList<>()).add(res);
                        break;
                    case COMMIT:
                        committedSeqs.add(header.getRefSeq());
                        break;
                }
            }
        } catch (Exception e) {
            log.error("[{}] 저널 스캔 중 오류", ticker, e);
        }

        // [Pass 2] 순차 리플레이: 결과(RES)가 있다면 강제 적용 + 미결 건(No COMMIT) 및 상태 복구 필요 건 리플레이
        int replayCount = 0;
        for (Map.Entry<Long, JournalReader.JournalEntry> cmdEntryEntry : cmdMap.entrySet()) {
            long seqNo = cmdEntryEntry.getKey();
            JournalReader.JournalEntry cmdEntry = cmdEntryEntry.getValue();
            List<ExecutionResult> results = resMap.get(seqNo);

            try {
                Object payload = JournalSerializer.deserialize(cmdEntry.getPayload());
                // 1. 명령 수행 및 상태 복구
                // 이미 COMMIT된 건이라도 스냅샷 이후의 명령이라면 오더북 상태 복구(Add Order 등)를 위해 재시행이 필요함.
                if (payload instanceof OrderRequest) {
                    OrderRequest or = (OrderRequest) payload;
                    replayCommand(ticker, orderManager, cmdEntry);
                    orderIdDeduplicator.checkAndMarkDuplicate(or.getOrderId(), or.getAction());
                } else if (payload instanceof TickDataEvent) {
                    if (results != null && !results.isEmpty()) {
                        // 과거 실체결 결과가 있다면 엔진 로직 대신 결과만 강제 적용 (Causality Protection)
                        for (ExecutionResult res : results) {
                            orderManager.applyExecutionResult(res);
                            String dedupAction = (res.getEventType() == EventType.CANCELLED) ? "CANCEL" : "CREATE";
                            orderIdDeduplicator.checkAndMarkDuplicate(res.getOrderId(), dedupAction);
                        }
                    } else if (!committedSeqs.contains(seqNo)) {
                        // 결과가 없고 커밋도 안 된 틱은 리플레이
                        replayCommand(ticker, orderManager, cmdEntry);
                    }
                } else if (payload instanceof MarketDataEvent) {
                    replayCommand(ticker, orderManager, cmdEntry);
                }

                // 2. 만약 과거 체결 결과(RES)가 주문 생성(CREATE)과 연관되어 있다면 다시 한 번 보정 적용
                // (위의 replayCommand가 addOrder를 수행했으므로, applyExecutionResult를 통해 정확한 잔량으로 보정함)
                if (results != null && !results.isEmpty() && payload instanceof OrderRequest) {
                    for (ExecutionResult res : results) {
                        orderManager.applyExecutionResult(res);
                    }
                }
                
                replayCount++;
            } catch (Exception e) {
                log.error("[{}] 명령 리플레이 실패 (Seq: {})", ticker, seqNo, e);
            }
        }

        if (replayCount > 0) {
            log.info("[{}] {}개의 명령(CMD) 재주행 완료 (결과 기반 복구 포함).", ticker, replayCount);
        }

        // 복구 완료 시점에 현재 시장 상태가 CLOSE라면 미체결 주문 일괄 취소 (장 종료 보장)
        if (!marketStateManager.isMarketOpen()) {
            log.info("[{}] 복구 시점 시장 상태가 CLOSE이므로 모든 미체결 주문 일괄 취소를 시작합니다.", ticker);
            orderManager.cancelAllOrders(startSeqNo + cmdMap.size()); // 마지막 시퀀스 번호 기반으로 수행
        }
    }

    /**
     * 개별 저널 항목(Entry)을 실제 엔진 상태에 반영합니다.
     * 
     * @param ticker 종목 코드
     * @param orderManager 해당 종목의 엔진 매니저
     * @param entry 재현할 저널 엔트리
     * @throws Exception 역직렬화 또는 실행 중 발생한 예외
     */
    private void replayCommand(String ticker, PendingOrderManager orderManager, JournalReader.JournalEntry entry) throws Exception {
        Object payload = JournalSerializer.deserialize(entry.getPayload());
        long seqNo = entry.getHeader().getSeqNo();

        if (payload instanceof OrderRequest) {
            OrderRequest order = (OrderRequest) payload;
            if ("CANCEL".equalsIgnoreCase(order.getAction())) {
                orderManager.cancelOrder(order.getOrderId(), seqNo);
            } else {
                orderManager.addOrder(order);
            }
        } else if (payload instanceof TickDataEvent) {
            TickDataEvent tick = (TickDataEvent) payload;
            orderManager.matchWithTick(tick, seqNo);
        } else if (payload instanceof MarketDataEvent) {
            MarketDataEvent mkt = (MarketDataEvent) payload;
            orderManager.updateMarketData(mkt);
        }
    }
}
