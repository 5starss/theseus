package kafka

import (
	"context"
	"encoding/json"
	"fmt"
	"log"

	"market-server/internal/config"

	"github.com/segmentio/kafka-go"
)

// Producer Kafka 메시지 발행기
type Producer struct {
	writers map[string]*kafka.Writer
	cfg     config.KafkaConfig
}

// NewProducer 설정된 브로커와 토픽들을 기반으로 Kafka Producer를 초기화한다.
func NewProducer(cfg config.KafkaConfig) *Producer {
	writers := make(map[string]*kafka.Writer)

	// 사용할 토픽 목록 (현재가, 호가)
	topics := []string{cfg.TickTopic, cfg.OrderbookTopic}

	for _, topic := range topics {
		writers[topic] = &kafka.Writer{
			Addr:                   kafka.TCP(cfg.Brokers...),
			Topic:                  topic,
			Balancer:               &kafka.LeastBytes{},
			AllowAutoTopicCreation: true,
			Async:                  true, // 비동기 전송 처리
		}
	}

	log.Printf("Kafka Producer initialized for brokers: %v", cfg.Brokers)

	return &Producer{
		writers: writers,
		cfg:     cfg,
	}
}

// PublishTick 체결가(Tick) 데이터를 Kafka에 발행한다.
func (p *Producer) PublishTick(ctx context.Context, payload interface{}) error {
	return p.publish(ctx, p.cfg.TickTopic, payload)
}

// PublishOrderbook 호가(Orderbook) 데이터를 Kafka에 발행한다.
func (p *Producer) PublishOrderbook(ctx context.Context, payload interface{}) error {
	return p.publish(ctx, p.cfg.OrderbookTopic, payload)
}

// publish 내부 공통 발행 로직
func (p *Producer) publish(ctx context.Context, topic string, payload interface{}) error {
	writer, exists := p.writers[topic]
	if !exists {
		return fmt.Errorf("kafka writer for topic %s not found", topic)
	}

	data, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("marshal payload for %s: %w", topic, err)
	}

	msg := kafka.Message{
		Value: data,
	}

	if err := writer.WriteMessages(ctx, msg); err != nil {
		return fmt.Errorf("write kafka message to %s: %w", topic, err)
	}

	return nil
}

// Close 시스템 종료 시(Graceful Shutdown) 모든 Kafka Writer를 닫는다.
func (p *Producer) Close() error {
	var errs []error
	for topic, writer := range p.writers {
		if err := writer.Close(); err != nil {
			errs = append(errs, fmt.Errorf("close writer for %s: %w", topic, err))
		}
	}

	if len(errs) > 0 {
		return fmt.Errorf("kafka producer close errors: %v", errs)
	}

	log.Printf("Kafka Producer closed successfully")
	return nil
}
