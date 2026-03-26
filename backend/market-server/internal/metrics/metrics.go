package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	// 체결(Tick) 메시지 처리 카운터
	TickMessagesProcessed = promauto.NewCounter(prometheus.CounterOpts{
		Name: "market_tick_messages_total",
		Help: "Total number of KIS tick messages processed",
	})

	// 호가(Orderbook) 메시지 처리 카운터
	OrderbookMessagesProcessed = promauto.NewCounter(prometheus.CounterOpts{
		Name: "market_orderbook_messages_total",
		Help: "Total number of KIS orderbook messages processed",
	})

	// 현재 WebSocket 연결 수 (클라이언트)
	WSConnections = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "market_ws_connections_active",
		Help: "Current number of active WebSocket client connections",
	})

	// Kafka Publish 에러 카운터
	KafkaPublishErrors = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "market_kafka_publish_errors_total",
		Help: "Total number of Kafka publish errors by topic",
	}, []string{"topic"})

	// Redis 에러 카운터
	RedisErrors = promauto.NewCounterVec(prometheus.CounterOpts{
		Name: "market_redis_errors_total",
		Help: "Total number of Redis errors by operation",
	}, []string{"operation"})

	// KIS WebSocket raw 수신 카운터 (처리 전 단계) — 진단용
	// TickMessagesProcessed와 비교하면 파이프라인 어디서 드롭되는지 파악 가능
	KISRawMessagesReceived = promauto.NewCounter(prometheus.CounterOpts{
		Name: "market_kis_raw_messages_total",
		Help: "Total raw messages received from KIS WebSocket (before parsing)",
	})

	// WSPool 공유 채널 현재 점유율 Gauge — 배압(backpressure) 모니터링용
	WSPoolChannelLen = promauto.NewGauge(prometheus.GaugeOpts{
		Name: "market_wspool_channel_len",
		Help: "Current number of messages buffered in WSPool shared channel",
	})
)

