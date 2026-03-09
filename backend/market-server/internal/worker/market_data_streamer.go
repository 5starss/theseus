package worker

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"

	"market-server/internal/service"
	"market-server/pkg/kafka"
)

// MarketDataStreamer Kafka에서 메시지를 읽어 WSHub로 브로드캐스트하는 역할을 담당한다.
type MarketDataStreamer struct {
	kafkaConsumer  *kafka.Consumer
	wsHub          *service.WSHub
	tickTopic      string
	orderbookTopic string
	wg             sync.WaitGroup
}

// NewMarketDataStreamer 새로운 MarketDataStreamer 인스턴스를 생성한다.
func NewMarketDataStreamer(kc *kafka.Consumer, hub *service.WSHub, tickTopic, orderbookTopic string) *MarketDataStreamer {
	return &MarketDataStreamer{
		kafkaConsumer:  kc,
		wsHub:          hub,
		tickTopic:      tickTopic,
		orderbookTopic: orderbookTopic,
	}
}

// Start Kafka로부터 TICK 및 ORDERBOOK 데이터를 비동기적으로 소비(Consume)하기 시작한다.
func (s *MarketDataStreamer) Start(ctx context.Context) {
	s.wg.Add(2)

	// TICK 스트리밍 처리 고루틴
	go func() {
		defer s.wg.Done()
		log.Printf("Starting MarketDataStreamer for TICK (topic: %s)", s.tickTopic)
		s.kafkaConsumer.StartConsume(ctx, s.tickTopic, s.handleTickMessage)
	}()

	// ORDERBOOK 스트리밍 처리 고루틴
	go func() {
		defer s.wg.Done()
		log.Printf("Starting MarketDataStreamer for ORDERBOOK (topic: %s)", s.orderbookTopic)
		s.kafkaConsumer.StartConsume(ctx, s.orderbookTopic, s.handleOrderbookMessage)
	}()
}

// handleTickMessage TICK 카프카 메시지를 수신했을 때 호출되는 콜백
func (s *MarketDataStreamer) handleTickMessage(ctx context.Context, value []byte) error {
	var tick Tick
	if err := json.Unmarshal(value, &tick); err != nil {
		return fmt.Errorf("failed to unmarshal tick raw message: %w", err)
	}

	// 클라이언트에 브로드캐스트하기 위한 페이로드 포맷팅
	payload, _ := json.Marshal(map[string]interface{}{
		"topic": service.TopicTick, // "TICK"
		"data":  tick,
	})

	// WSHub에 TICK 단건 브로드캐스트 요청 (구독키: "TICK:005930")
	topicKey := service.TopicTick + ":" + tick.Ticker
	s.wsHub.Broadcast(topicKey, payload)

	return nil
}

// handleOrderbookMessage ORDERBOOK 카프카 메시지를 수신했을 때 호출되는 콜백
func (s *MarketDataStreamer) handleOrderbookMessage(ctx context.Context, value []byte) error {
	var ob Orderbook
	if err := json.Unmarshal(value, &ob); err != nil {
		return fmt.Errorf("failed to unmarshal orderbook raw message: %w", err)
	}

	// 클라이언트에 브로드캐스트하기 위한 페이로드 포맷팅
	payload, _ := json.Marshal(map[string]interface{}{
		"topic": service.TopicOrderbook, // "ORDERBOOK"
		"data":  ob,
	})

	// WSHub에 ORDERBOOK 단건 브로드캐스트 요청 (구독키: "ORDERBOOK:005930")
	topicKey := service.TopicOrderbook + ":" + ob.Ticker
	s.wsHub.Broadcast(topicKey, payload)

	return nil
}

// Wait 모든 소비 루프가 안전하게 종료될 때까지 대기(Block)한다.
func (s *MarketDataStreamer) Wait() {
	s.wg.Wait()
}
