package com.s14p21a503.coreapi.domain.market.service;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.s14p21a503.coreapi.common.exception.CustomException;
import com.s14p21a503.coreapi.common.kafka.KafkaTopicConstants;
import com.s14p21a503.coreapi.common.response.status.ErrorCode;
import com.s14p21a503.coreapi.domain.market.dto.MarketControlEvent;
import com.s14p21a503.coreapi.domain.market.entity.Holiday;
import com.s14p21a503.coreapi.domain.market.repository.HolidayRepository;
import com.s14p21a503.coreapi.domain.outbox.entity.OutboxEvent;
import com.s14p21a503.coreapi.domain.outbox.repository.OutboxEventRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class MarketService {

    private final OutboxEventRepository outboxEventRepository;
    private final HolidayRepository holidayRepository;
    private final HolidayManager holidayManager;
    private final ObjectMapper objectMapper;

    /**
     * 시장 개장 명령을 아웃박스에 저장합니다.
     */
    @Transactional
    public void openMarket() {
        // 매일 아침 개장 시 현재 DB에 등록된 최신 휴장일 리스트를 함께 전파하여 정합성 강화
        List<String> currentHolidays = new java.util.ArrayList<>(holidayManager.getHolidayDates());
        saveControlEvent(MarketControlEvent.ControlType.MARKET_OPEN, null, currentHolidays);
    }

    /**
     * 시장 종료 명령을 아웃박스에 저장합니다.
     */
    @Transactional
    public void closeMarket() {
        saveControlEvent(MarketControlEvent.ControlType.MARKET_CLOSE, null, null);
    }

    /**
     * 일시 정지(HALT) 명령을 아웃박스에 저장합니다.
     */
    @Transactional
    public void haltMarket() {
        saveControlEvent(MarketControlEvent.ControlType.MARKET_HALT, null, null);
    }

    /**
     * 일시 정지 해제(RESUME) 명령을 아웃박스에 저장합니다.
     */
    @Transactional
    public void resumeMarket() {
        saveControlEvent(MarketControlEvent.ControlType.MARKET_RESUME, null, null);
    }

    /**
     * 현재 DB의 최신 휴장일 리스트를 매칭 엔진으로 강제 전파합니다. (수동 동기화용)
     */
    @Transactional
    public void syncHolidays() {
        List<String> currentHolidays = new java.util.ArrayList<>(holidayManager.getHolidayDates());
        saveControlEvent(MarketControlEvent.ControlType.SET_HOLIDAYS, null, currentHolidays);
        log.info("수동 휴장일 동기화 이벤트를 발행했습니다. ({}건)", currentHolidays.size());
    }


    /**
     * 시장 제어 이벤트를 생성하여 아웃박스(Outbox) 테이블에 저장합니다.
     * 이 메서드는 트랜잭션 내에서 실행되며, 향후 아웃박스 스케줄러에 의해 카프카(Kafka)로 발행됩니다.
     *
     * @param type         제어 타입 (OPEN, CLOSE, HALT, RESUME)
     * @param ticker       특정 종목 코드 (null이면 전 종목 대상)
     * @param holidayDates 전파할 휴장일 리스트 (null이면 포함하지 않음)
     */
    private void saveControlEvent(MarketControlEvent.ControlType type, String ticker, List<String> holidayDates) {
        // 개장(OPEN) 또는 명시적 동기화(SET_HOLIDAYS) 명령 시에만 휴장 정보를 포함하여 네트워크 부하를 줄입니다.
        try {
            // 1. 이벤트 DTO 생성
            MarketControlEvent event = MarketControlEvent.builder()
                    .type(type)
                    .ticker(ticker)
                    .timestamp(System.currentTimeMillis())
                    .holidayDates(holidayDates)
                    .build();

            // 2. 카프카 페이로드 직렬화
            String payload = objectMapper.writeValueAsString(event);

            // 3. 아웃박스(Outbox) 엔티티 생성 및 저장
            // 이 데이터는 별도의 스케줄러(OutboxPollingScheduler)가 읽어서 카프카의 'market-control' 토픽으로 전달합니다.
            OutboxEvent outboxEvent = OutboxEvent.builder()
                    .aggregateType("MARKET")
                    .aggregateId("SYSTEM") // 글로벌 제어이므로 ID는 고정
                    .topic(KafkaTopicConstants.MARKET_CONTROL_EVENT_TOPIC)
                    .messageKey("GLOBAL") // 모든 엔진이 동일하게 받도록 키 고정
                    .payload(payload)
                    .build();

            outboxEventRepository.save(outboxEvent);
            log.info("시장 제어 이벤트 아웃박스 저장 완료: {}", type);
        } catch (JsonProcessingException e) {
            log.error("시장 제어 이벤트 직렬화 실패", e);
            throw new CustomException(ErrorCode.INTERNAL_SERVER_ERROR);
        }
    }
}
