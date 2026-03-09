package com.s14p21a503.matcher.journal;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import jakarta.annotation.PreDestroy;
import java.io.IOException;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * 종목별 Journaler 관리 서비스.
 */
@Slf4j
@Service
public class JournalService {
    
    @Value("${matcher.journal.dir:./logs}")
    private String logDir;

    private final Map<String, UnifiedJournaler> journalers = new ConcurrentHashMap<>();
    private final Map<String, ExecutorService> executors = new ConcurrentHashMap<>();

    /**
     * 특정 종목(Ticker)에 해당하는 UnifiedJournaler 인스턴스를 반환합니다.
     * 해당 종목의 저널러가 메모리에 없으면 새 인스턴스를 생성하여 반환합니다.
     * 
     * @param ticker 종목 코드 (예: "005930")
     * @return 해당 종목의 UnifiedJournaler 인스턴스
     */
    public UnifiedJournaler getJournaler(String ticker) {
        return journalers.computeIfAbsent(ticker, t -> {
            try {
                return new UnifiedJournaler(t, logDir);
            } catch (IOException e) {
                log.error("[{}] 저널러 생성 실패", t, e);
                throw new RuntimeException("저널러 생성 실패", e);
            }
        });
    }

    /**
     * 특정 종목(Ticker) 전용의 단일 스레드 Executor를 반환합니다.
     * 모든 엔진 입고 및 후속 처리가 이 스레드에서 순차적으로 실행됨을 보장합니다.
     */
    public ExecutorService getExecutor(String ticker) {
        return executors.computeIfAbsent(ticker, t -> 
            Executors.newSingleThreadExecutor(r -> new Thread(r, "TickerExecutor-" + t))
        );
    }

    /**
     * 특정 종목의 저널 파일을 로테이트(비우기) 처리합니다.
     * 스냅샷 저장 후 과거 로그가 더 이상 필요 없을 때 호출됩니다.
     * 
     * @param ticker 로테이트할 종목 코드
     */
    public void rotateJournal(String ticker) {
        UnifiedJournaler j = journalers.get(ticker);
        if (j != null) {
            try {
                j.truncateJournal();
            } catch (IOException e) {
                log.error("[{}] 저널 로테이션 실패", ticker, e);
            }
        }
    }

    /**
     * 특정 종목의 저널러를 안전하게 닫고 관리 대상에서 제거합니다.
     * 
     * @param ticker 닫을 종목 코드
     */
    public void closeJournaler(String ticker) {
        UnifiedJournaler j = journalers.remove(ticker);
        if (j != null) {
            try {
                j.close();
            } catch (IOException e) {
                log.error("[{}] 저널러 닫기 중 오류 발생", ticker, e);
            }
        }
    }

    /**
     * Spring 컨테이너 종료 시 호출되어, 
     * 현재 열려있는 모든 종목의 저널러를 안전하게 닫습니다.
     */
    @PreDestroy
    public void shutdown() {
        log.info("JournalService 종료 및 모든 자원(저널러, Executor) 정리 시작...");
        
        // 1. 저널러 닫기
        journalers.values().forEach(j -> {
            try {
                j.close();
            } catch (IOException e) {
                log.error("저널러 닫기 중 오류 발생", e);
            }
        });
        journalers.clear();

        // 2. Executor 종료
        executors.values().forEach(ExecutorService::shutdown);
        executors.clear();
        
        log.info("JournalService 모든 자원 정리 완료.");
    }
}
