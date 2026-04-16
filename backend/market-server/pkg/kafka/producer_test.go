package kafka

import (
	"context"
	"testing"

	"market-server/internal/config"

	"github.com/segmentio/kafka-go"
)

func testKafkaConfig() config.KafkaConfig {
	return config.KafkaConfig{
		Brokers:        []string{"localhost:9092"},
		TickTopic:      "test.tick",
		OrderbookTopic: "test.orderbook",
	}
}

// TestNewProducer_HashBalancer_AllTopics 모든 토픽의 Writer가 Hash 발란서로 설정되는지 확인한다.
// Hash 발란서는 동일 Ticker 메시지를 항상 같은 파티션으로 라우팅하여 순서를 보장한다.
func TestNewProducer_HashBalancer_AllTopics(t *testing.T) {
	cfg := testKafkaConfig()
	p := NewProducer(cfg)
	defer p.Close()

	topics := []string{cfg.TickTopic, cfg.OrderbookTopic}
	for _, topic := range topics {
		writer, exists := p.writers[topic]
		if !exists {
			t.Errorf("topic %s의 writer가 없음", topic)
			continue
		}
		if _, ok := writer.Balancer.(*kafka.Hash); !ok {
			t.Errorf("topic %s: Hash 발란서를 기대했지만 %T 설정됨", topic, writer.Balancer)
		}
	}
}

// TestNewProducer_AsyncMode 모든 Writer가 비동기 모드로 설정되는지 확인한다.
func TestNewProducer_AsyncMode(t *testing.T) {
	p := NewProducer(testKafkaConfig())
	defer p.Close()

	for topic, writer := range p.writers {
		if !writer.Async {
			t.Errorf("topic %s: Async 모드가 비활성화됨", topic)
		}
	}
}

// TestNewProducer_TopicCount 설정된 토픽(TICK + ORDERBOOK) 수만큼 Writer가 생성되는지 확인한다.
func TestNewProducer_TopicCount(t *testing.T) {
	p := NewProducer(testKafkaConfig())
	defer p.Close()

	const expected = 2 // TickTopic + OrderbookTopic
	if len(p.writers) != expected {
		t.Errorf("writer 수 불일치: got %d, want %d", len(p.writers), expected)
	}
}

// TestPublish_UnknownTopic_ReturnsError 존재하지 않는 토픽으로 발행 시 에러를 반환해야 한다.
func TestPublish_UnknownTopic_ReturnsError(t *testing.T) {
	p := NewProducer(testKafkaConfig())
	defer p.Close()

	err := p.publish(context.Background(), "unknown.topic", map[string]string{"k": "v"}, "005930")
	if err == nil {
		t.Fatal("알 수 없는 토픽에 에러가 반환되지 않음")
	}
}

// TestPublish_UnmarshalablePayload_ReturnsError JSON 직렬화 불가한 페이로드 발행 시 에러를 반환해야 한다.
func TestPublish_UnmarshalablePayload_ReturnsError(t *testing.T) {
	p := NewProducer(testKafkaConfig())
	defer p.Close()

	// channel 타입은 JSON 직렬화 불가
	err := p.publish(context.Background(), "test.tick", make(chan int), "005930")
	if err == nil {
		t.Fatal("직렬화 불가 페이로드에서 에러가 반환되지 않음")
	}
}
