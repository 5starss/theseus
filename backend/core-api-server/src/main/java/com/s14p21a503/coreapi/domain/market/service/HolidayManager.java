package com.s14p21a503.coreapi.domain.market.service;

import com.s14p21a503.coreapi.domain.market.entity.Holiday;
import com.s14p21a503.coreapi.domain.market.repository.HolidayRepository;
import jakarta.annotation.PostConstruct;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.time.LocalDate;
import java.util.Collections;
import java.util.List;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;

/**
 * 전역 휴장일 관리자
 * 글로벌 스케줄러가 휴장일에는 개장 신호를 보내지 않도록 관리합니다.
 */
@Slf4j
@RequiredArgsConstructor
@Component
public class HolidayManager {

    private final HolidayRepository holidayRepository;
    private final Set<String> holidayDates = Collections.newSetFromMap(new ConcurrentHashMap<>());

    @PostConstruct
    public void loadHolidaysFromDb() {
        List<Holiday> holidays = holidayRepository.findAll();
        Set<String> dates = holidays.stream()
                .map(h -> h.getDate().toString())
                .collect(java.util.stream.Collectors.toSet());
        updateHolidays(dates);
        log.info("DB로부터 {}건의 휴장일을 로드했습니다.", dates.size());
    }

    public boolean isHoliday(LocalDate date) {
        return holidayDates.contains(date.toString());
    }

    public void updateHolidays(Set<String> newHolidays) {
        if (newHolidays == null) return;
        this.holidayDates.clear();
        this.holidayDates.addAll(newHolidays);
        log.info("전역 휴장일 리스트가 업데이트되었습니다: {}건", holidayDates.size());
    }

    public Set<String> getHolidayDates() {
        return Collections.unmodifiableSet(holidayDates);
    }
}
