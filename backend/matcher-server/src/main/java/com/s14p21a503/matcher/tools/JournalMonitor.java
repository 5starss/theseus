package com.s14p21a503.matcher.tools;

import com.s14p21a503.matcher.dto.ExecutionResult;
import com.s14p21a503.matcher.dto.MarketDataEvent;
import com.s14p21a503.matcher.dto.OrderRequest;
import com.s14p21a503.matcher.dto.TickDataEvent;
import com.s14p21a503.matcher.journal.JournalReader;
import com.s14p21a503.matcher.journal.JournalSerializer;
import com.s14p21a503.matcher.journal.JournalHeader;

import java.io.File;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;

/**
 * 전용 저널 모니터링 툴.
 * 실행: java -cp ... com.s14p21a503.matcher.tools.JournalMonitor [ticker] [logDir]
 */
public class JournalMonitor {

    private static final DateTimeFormatter FORMATTER = DateTimeFormatter.ofPattern("HH:mm:ss.SSS")
            .withZone(ZoneId.systemDefault());

    // ANSI Colors
    public static final String ANSI_RESET = "\u001B[0m";
    public static final String ANSI_CYAN = "\u001B[36m";
    public static final String ANSI_GREEN = "\u001B[32m";
    public static final String ANSI_YELLOW = "\u001B[33m";
    public static final String ANSI_RED = "\u001B[31m";
    public static final String ANSI_PURPLE = "\u001B[35m";

    public static void main(String[] args) throws Exception {
        String ticker = args.length > 0 ? args[0] : "005930";
        String logDir = args.length > 1 ? args[1] : "c:/MATERCHER-DATA"; // 기본값
        Path logPath = Paths.get(logDir, ticker, "journal.log");

        File logFile = logPath.toFile();
        if (!logFile.exists()) {
            System.err.println("로그 파일을 찾을 수 없습니다: " + logFile.getAbsolutePath());
            return;
        }

        System.out.println(ANSI_CYAN + "================================================================================================" + ANSI_RESET);
        System.out.println(ANSI_CYAN + "  🚀 Matcher Journal Monitor - Ticker: [" + ticker + "]" + ANSI_RESET);
        System.out.println(ANSI_CYAN + "  📍 Path: " + logFile.getAbsolutePath() + ANSI_RESET);
        System.out.println(ANSI_CYAN + "  (Press Ctrl+C to stop)" + ANSI_RESET);
        System.out.println(ANSI_CYAN + "================================================================================================");
        System.out.printf("%-6s | %-12s | %-6s | %-15s | %-7s | %s%n", 
            "SEQ", "TIME", "TYPE", "K-META(P/O)", "REF", "PAYLOAD");
        System.out.println("------------------------------------------------------------------------------------------------" + ANSI_RESET);

        try (JournalReader reader = new JournalReader(ticker, logPath)) {
            while (true) {
                JournalReader.JournalEntry entry = reader.readNext();
                if (entry == null) {
                    // EOF 도달 시 잠시 대기 후 다시 시도 (Tail 모드)
                    Thread.sleep(200);
                    continue;
                }

                JournalHeader header = entry.getHeader();
                Object payload = JournalSerializer.deserialize(entry.getPayload());
                String timeStr = FORMATTER.format(Instant.ofEpochMilli(header.getTimestamp()));
                
                String typeColor = switch (header.getType()) {
                    case CMD -> ANSI_YELLOW;
                    case RES -> ANSI_GREEN;
                    case COMMIT -> ANSI_PURPLE;
                    default -> ANSI_RESET;
                };

                String kmeta = String.format("P:%d/O:%d", header.getPartition(), header.getOffset());

                System.out.printf("[%d] %s | %s%-6s%s | %-15s | %-7d | %s%n", 
                        header.getSeqNo(), 
                        timeStr, 
                        typeColor, header.getType(), ANSI_RESET,
                        kmeta,
                        header.getRefSeq(),
                        formatPayload(payload));
            }
        }
    }

    private static String formatPayload(Object payload) {
        if (payload == null) return "-";
        if (payload instanceof OrderRequest or) {
            String color = or.getAction().equals("BUY") ? ANSI_RED : ANSI_CYAN;
            return String.format("%sOrder(ID:%d, %s, %s, Q:%d)%s", 
                    color, or.getOrderId(), or.getAction(), or.getPrice(), or.getRequestedQuantity(), ANSI_RESET);
        }
        if (payload instanceof TickDataEvent td) {
            return String.format(ANSI_GREEN + "Tick(P:%s, Q:%d)" + ANSI_RESET, td.getPrice(), td.getQty());
        }
        if (payload instanceof MarketDataEvent md) {
            return String.format("MktData(B:%s, A:%s)", md.getBestBid(), md.getBestAsk());
        }
        if (payload instanceof ExecutionResult er) {
            return String.format(ANSI_YELLOW + "Result(ID:%d, P:%s, Q:%d)" + ANSI_RESET, 
                    er.getOrderId(), er.getMatchPrice(), er.getMatchQuantity());
        }
        return payload.toString();
    }
}
