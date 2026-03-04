package com.s14p21a503.coreapi.common.kafka;

public final class KafkaTopicConstants {

    private KafkaTopicConstants() {
        // 상수 유틸리티 클래스이므로 인스턴스화 방지
    }

    // =========================
    // 1. 코어 API 서버 -> 카프카 브로커 -> 체결 엔진 서버 (발행 토픽)
    // =========================
    /**
     * 주문 이벤트 토픽
     * 코어 API 서버가 유저/잔고 검증 후 '주문 이벤트'를 발행하면,
     * 체결 엔진 서버가 이를 구독하여 인메모리 매칭을 진행합니다.
     */
    public static final String ORDER_EVENT_TOPIC = "order-events";

    /**
     * 주문 취소 이벤트 토픽
     * 코어 API 서버가 주문 취소를 접수하면,
     * 체결 엔진 서버가 이를 구독하여 매칭 대기열에서 제거합니다.
     */
    public static final String ORDER_CANCEL_EVENT_TOPIC = "order-cancel-events";

    // =========================
    // 2. 체결 엔진 서버 -> 카프카 브로커 -> 코어 API 서버 (구독 토픽)
    // =========================
    /**
     * 체결 이벤트 토픽
     * 체결 엔진 서버에서 매칭 후 '체결 완료 이벤트'를 발행하면,
     * 코어 API 서버가 이를 구독하여 유저의 실질 잔고 및 주식 원장을 최종 업데이트합니다.
     */
    public static final String EXECUTION_EVENT_TOPIC = "execution-events";

}
