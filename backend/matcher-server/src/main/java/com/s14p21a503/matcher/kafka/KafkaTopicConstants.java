package com.s14p21a503.matcher.kafka;

public final class KafkaTopicConstants {

    private KafkaTopicConstants() {
        // 상수 유틸리티 클래스이므로 인스턴스화 방지
    }

    /**
     * 주문 이벤트 토픽
     */
    public static final String ORDER_EVENT_TOPIC = "order-events";

    /**
     * 주문 취소 이벤트 토픽
     */
    public static final String ORDER_CANCEL_EVENT_TOPIC = "order-cancel-events";

    /**
     * 체결 이벤트 토픽
     */
    public static final String EXECUTION_EVENT_TOPIC = "execution-events";

    /**
     * 호가창/시세 데이터 토픽 (체결 엔진 전용)
     * TODO: 시세 서버(Market Server) 사양에 따라 토픽명이 변경될 수 있음
     */
    public static final String MARKET_DATA_EVENT_TOPIC = "market-data-event";

    /**
     * 체결 데이터 토픽 (체결 엔진 전용)
     * TODO: 시세 서버(Market Server) 사양에 따라 토픽명이 변경될 수 있음
     */
    public static final String TRADE_DATA_EVENT_TOPIC = "trade-data-event";
}
