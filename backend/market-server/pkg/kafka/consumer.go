package kafka

import (
	"context"
	"log"

	"market-server/internal/config"

	"github.com/segmentio/kafka-go"
)

// Consumer Kafka 메시지 구독기
type Consumer struct {
	readers map[string]*kafka.Reader
	cfg     config.KafkaConfig
}

// NewConsumer 설정된 브로커와 토픽들을 기반으로 Kafka Consumer를 초기화한다.
func NewConsumer(cfg config.KafkaConfig, groupID string) *Consumer {
	readers := make(map[string]*kafka.Reader)

	topics := []string{cfg.TickTopic, cfg.OrderbookTopic}

	for _, topic := range topics {
		readers[topic] = kafka.NewReader(kafka.ReaderConfig{
			Brokers:  cfg.Brokers,
			GroupID:  groupID,
			Topic:    topic,
			MinBytes: 10e3, // 10KB
			MaxBytes: 10e6, // 10MB
		})
	}

	log.Printf("Kafka Consumer initialized for brokers: %v, group: %s", cfg.Brokers, groupID)

	return &Consumer{
		readers: readers,
		cfg:     cfg,
	}
}

// StartConsume 지정된 토픽의 메시지를 읽어 handler 콜백 함수로 전달한다.
func (c *Consumer) StartConsume(ctx context.Context, topic string, handler func(context.Context, []byte) error) {
	reader, exists := c.readers[topic]
	if !exists {
		log.Printf("Error: kafka reader for topic %s not found", topic)
		return
	}

	for {
		// 컨텍스트가 취소되었는지 확인
		select {
		case <-ctx.Done():
			log.Printf("Consumer for topic %s stopped by context", topic)
			return
		default:
		}

		m, err := reader.FetchMessage(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return // ctx 취소에 의한 에러라면 정상 종료
			}
			log.Printf("Error fetching message from %s: %v", topic, err)
			continue
		}

		if err := handler(ctx, m.Value); err != nil {
			// 핸들러 에러(예: JSON 파싱 실패)는 영구 오류이므로 건너뛰고 커밋
			// 커밋 없이 continue 하면 재시작 시 동일 메시지가 무한 재전달(Poison Pill)됨
			log.Printf("Error handling message from %s (poison pill skip): %v", topic, err)
		}

		// 처리 결과에 관계없이 오프셋 커밋 (Poison Pill 무한 재시도 방지)
		if err := reader.CommitMessages(ctx, m); err != nil {
			log.Printf("Error committing message from %s: %v", topic, err)
		}
	}
}

// Close 시스템 종료 시(Graceful Shutdown) 모든 Kafka Reader를 닫는다.
func (c *Consumer) Close() error {
	for topic, reader := range c.readers {
		if err := reader.Close(); err != nil {
			log.Printf("Error closing reader for %s: %v", topic, err)
		}
	}
	log.Printf("Kafka Consumer closed successfully")
	return nil
}
