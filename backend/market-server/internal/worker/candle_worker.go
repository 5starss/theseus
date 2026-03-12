package worker

import (
	"context"
	"encoding/json"
	"log"
	"sync"
	"time"

	"market-server/internal/domain"
	"market-server/internal/repository"
	"market-server/pkg/kafka"
)

// CandleWorker Kafka에서 TICK을 읽어 1분봉으로 집계한 뒤 MySQL에 벌크 인서트한다.
type CandleWorker struct {
	consumer  *kafka.Consumer
	stockRepo *repository.StockRepository
	topic     string

	mu      sync.Mutex
	candles map[string]*domain.Candle
	
	wg          sync.WaitGroup
	ctx         context.Context
	cancel      context.CancelFunc
	flushTicker *time.Ticker
}

func NewCandleWorker(c *kafka.Consumer, repo *repository.StockRepository, tickTopic string) *CandleWorker {
	ctx, cancel := context.WithCancel(context.Background())
	return &CandleWorker{
		consumer:  c,
		stockRepo: repo,
		topic:     tickTopic,
		candles:   make(map[string]*domain.Candle),
		ctx:       ctx,
		cancel:    cancel,
	}
}

func (w *CandleWorker) Start(ctx context.Context) {
	// Sync the ticker to start exactly on the next minute boundary
	now := time.Now()
	nextMinute := now.Truncate(time.Minute).Add(time.Minute)
	durationUntilNextMinute := time.Until(nextMinute)
	
	w.wg.Add(2)
	
	go func() {
		defer w.wg.Done()
		log.Printf("Starting CandleWorker for TICK (topic: %s)", w.topic)
		w.consumer.StartConsume(w.ctx, w.topic, w.handleTick)
	}()

	go func() {
		defer w.wg.Done()
		// Wait until next minute
		select {
		case <-time.After(durationUntilNextMinute):
		case <-w.ctx.Done():
			return
		}
		
		w.flushTicker = time.NewTicker(time.Minute)
		log.Printf("CandleWorker flush timer started (sync'd to minute boundary)")
		
		for {
			select {
			case <-w.flushTicker.C:
				w.flushCandles()
			case <-w.ctx.Done():
				if w.flushTicker != nil {
					w.flushTicker.Stop()
				}
				// 셧다운 시 남은 캔들 플러시 (Graceful Shutdown 백업 보장)
				w.flushCandles()
				return
			}
		}
	}()
}

func (w *CandleWorker) handleTick(ctx context.Context, value []byte) error {
	var tick Tick
	if err := json.Unmarshal(value, &tick); err != nil {
		return err
	}

	if tick.Ticker == "" {
		return nil
	}

	ticker := tick.Ticker
	price := int64(tick.CurrentPrice)
	volume := tick.TradeVolume

	// 현재 시간 (분 단위로 절사된 시작 시간)
	currentTimestamp := time.Now().Truncate(time.Minute).Format("2006-01-02 15:04:00")

	w.mu.Lock()
	c, exists := w.candles[ticker]
	if !exists {
		// 해당 1분의 첫 체결
		w.candles[ticker] = &domain.Candle{
			Timestamp: currentTimestamp,
			Open:      price,
			High:      price,
			Low:       price,
			Close:     price,
			Volume:    volume,
		}
	} else {
		// 기존 캔들 업데이트
		if price > c.High {
			c.High = price
		}
		if price < c.Low {
			c.Low = price
		}
		c.Close = price
		c.Volume += volume
	}
	w.mu.Unlock()

	return nil
}

// flushCandles 메모리 버퍼를 스왑(Swap)하여 현재까지 쌓인 캔들 맵을 비우고 비동기로 DB에 Insert
func (w *CandleWorker) flushCandles() {
	// 1. Buffer Swap (빠른 Lock)
	w.mu.Lock()
	if len(w.candles) == 0 {
		w.mu.Unlock()
		return
	}
	
	// 현재 맵 복사(실제로는 포인터 레퍼런스 스왑)
	oldCandles := w.candles
	w.candles = make(map[string]*domain.Candle) // 새로운 빈 맵 할당
	w.mu.Unlock()
	
	// 2. Unlock 된 상태에서 비동기 / 여유롭게 DB Insert 진행
	// 타임아웃 컨텍스트 설정 (예: 5초)
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	err := w.stockRepo.BulkInsertCandles(ctx, oldCandles, domain.IntervalMinute)
	if err != nil {
		log.Printf("[CandleWorker] Failed to flush %d candles to DB: %v", len(oldCandles), err)
	} else {
		log.Printf("[CandleWorker] Flushed %d 1m candles into DB successfully", len(oldCandles))
	}
}

func (w *CandleWorker) Stop() {
	w.cancel()
	w.wg.Wait()
}
