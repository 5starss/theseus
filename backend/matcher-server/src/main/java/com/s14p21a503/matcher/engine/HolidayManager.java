package com.s14p21a503.matcher.engine;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.annotation.PostConstruct;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.io.File;
import java.io.IOException;
import java.time.LocalDate;
import java.util.Collections;
import java.util.Set;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 한국거래소(KRX) 휴장일 관리자.
 * 기본적으로 2026년 휴장일 데이터를 포함하며, 실시간 업데이트가 가능합니다.
 */
@Slf4j
@Component
public class HolidayManager {

    private final String HOLIDAY_FILE_PATH = "holidays.json";
    private final ObjectMapper objectMapper = new ObjectMapper();

    // YYYY-MM-DD 형식의 문자열 셋으로 관리 (LocalDate 변환 오버헤드 방지)
    private final Set<String> holidayDates = Collections.newSetFromMap(new ConcurrentHashMap<>());

    public HolidayManager() {
    }

    @PostConstruct
    public void init() {
        loadHolidaysFromDisk();
    }

    /**
     * 특정 날짜가 휴장일인지 확인합니다.
     */
    public boolean isHoliday(LocalDate date) {
        return holidayDates.contains(date.toString());
    }

    /**
     * 휴장일 리스트를 실시간으로 업데이트하고 비동기로 디스크에 저장합니다.
     */
    public synchronized void updateHolidays(Set<String> newHolidays) {
        if (newHolidays == null || newHolidays.isEmpty()) return;
        
        // 기존 데이터와 동일하면 작업을 건너뜀 (성능 최적화)
        if (this.holidayDates.equals(newHolidays)) {
            return;
        }

        this.holidayDates.clear();
        this.holidayDates.addAll(newHolidays);
        
        // 디스크 저장은 비동기로 수행하여 매칭 엔진 스레드 블로킹 방지
        CompletableFuture.runAsync(this::saveHolidaysToDisk);
        log.info("매칭 엔진 휴장일 리스트가 갱신 및 디스크 저장되었습니다: {}건", holidayDates.size());
    }

    private synchronized void saveHolidaysToDisk() {
        try {
            objectMapper.writeValue(new File(HOLIDAY_FILE_PATH), holidayDates);
        } catch (IOException e) {
            log.error("휴장일 디스크 저장 실패", e);
        }
    }

    private void loadHolidaysFromDisk() {
        File file = new File(HOLIDAY_FILE_PATH);
        if (!file.exists()) {
            log.info("로컬 휴장일 백업 파일이 존재하지 않습니다.");
            return;
        }

        try {
            Set<String> loadedHolidays = objectMapper.readValue(file, new TypeReference<Set<String>>() {});
            if (loadedHolidays != null) {
                this.holidayDates.addAll(loadedHolidays);
                log.info("로컬 디스크로부터 {}건의 휴장일을 복구했습니다.", holidayDates.size());
            }
        } catch (IOException e) {
            log.error("휴장일 디스크 로드 실패", e);
        }
    }
}
