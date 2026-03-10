package worker

import (
	"context"
	"encoding/json"
	"log"
	"sync"
	"time"

	"market-server/pkg/kafka"
	"market-server/pkg/kis"

	"github.com/redis/go-redis/v9"
)

// MarketDataWorker WebSocket 파이프라인에서 데이터를 읽어 Kafka와 Redis에 적재한다.
type MarketDataWorker struct {
	wsClient *kis.WSClient
	kafka    *kafka.Producer
	redis    *redis.Client
	wg       sync.WaitGroup
}

func NewMarketDataWorker(ws *kis.WSClient, k *kafka.Producer, r *redis.Client) *MarketDataWorker {
	return &MarketDataWorker{
		wsClient: ws,
		kafka:    k,
		redis:    r,
	}
}

// Start 워커 풀을 구동한다. workerCount 만큼의 고루틴이 띄워져서 버퍼드 채널을 병렬 처리한다.
func (w *MarketDataWorker) Start(ctx context.Context, workerCount int) {
	for i := 0; i < workerCount; i++ {
		w.wg.Add(1)
		go w.processLoop(ctx, i)
	}
	log.Printf("Started %d MarketDataWorker instances", workerCount)
}

func (w *MarketDataWorker) processLoop(ctx context.Context, id int) {
	defer w.wg.Done()

	var msgCount int64

	// 백그라운드 반복 루프
	// context가 취소되더라도(chan <-ctx.Done), 채널에 남아있는(Drain) 메시지를 전부 처리하고 종료해야 한다.
	// 따라서 for range 채널 방식을 사용하여 채널이 close 될 때까지 계속 읽도록 한다.
	for msg := range w.wsClient.MessageChan {
		rawStr := string(msg)

		// 1. 파싱
		parsedData, dataType, err := parseKISMessage(rawStr)
		if err != nil {
			log.Printf("[Worker %d] parse error: %v | raw: %.100s", id, err, rawStr)
			continue
		}

		if parsedData == nil {
			log.Printf("[Worker %d] ignored message (ping/control): %.100s", id, rawStr)
			continue
		}

		msgCount++

		// 2. Kafka 및 Redis 반영
		switch dataType {
		case "tick":
			tick := parsedData.(Tick)
			log.Printf("[KIS TICK #%d] Worker=%d ticker=%s name=%s price=%.0f rate=%.2f%% vol=%d",
				msgCount, id, tick.Ticker, tick.Name, tick.CurrentPrice, tick.ChangeRate, tick.AccVolume)
			// Kafka 푸시 (Ticker를 파티션 Key로 사용)
			w.kafka.PublishTick(context.Background(), tick, tick.Ticker) // worker graceful shutdown 독립 실행 위해 Background
			// Redis 반영
			w.updateTickToRedis(context.Background(), tick)

		case "orderbook":
			ob := parsedData.(Orderbook)
			log.Printf("[KIS ORDERBOOK #%d] Worker=%d ticker=%s name=%s ask=%.0f bid=%.0f",
				msgCount, id, ob.Ticker, ob.Name, ob.AskPrice1, ob.BidPrice1)
			w.kafka.PublishOrderbook(context.Background(), ob, ob.Ticker)
			w.updateOrderbookToRedis(context.Background(), ob)
		}
	}
	log.Printf("Worker %d stopped cleanly (channel drained), total processed: %d", id, msgCount)
}

// updateTickToRedis 체결가 데이터를 레디스에 저장하고 랭킹을 업데이트한다 (Redis Pipeline).
func (w *MarketDataWorker) updateTickToRedis(ctx context.Context, tick Tick) {
	pipe := w.redis.Pipeline()

	hashKey := "stocks:current:" + tick.Ticker

	// 현재가 단건 저장 (Hash) - 호가창/체결 워커 전용 캐시
	pipe.HSet(ctx, hashKey, map[string]interface{}{
		"price":       tick.CurrentPrice,
		"open":        tick.OpenPrice,
		"high":        tick.HighPrice,
		"low":         tick.LowPrice,
		"change_rate": tick.ChangeRate,
		"acc_vol":     tick.AccVolume,
		"name":        tick.Name,
	})

	// 전역 종목 정보 (stocks:info) 갱신 - GetTopByVolume(HOME_40) 조회용
	infoKey := "stocks:info:" + tick.Ticker
	pipe.HSet(ctx, infoKey, map[string]interface{}{
		"currentPrice": tick.CurrentPrice,
		"changeRate":   tick.ChangeRate,
		"accVolume":    tick.AccVolume,
		// ticker와 name 등은 BulkUpsertStocks 측에 존재하거나 여기서 추가로 덮어써도 무방함
		"ticker": tick.Ticker,
		"name":   tick.Name,
	})

	// 누적 거래량 랭킹 갱신 (Sorted Set)
	pipe.ZAdd(ctx, "stocks:rank:volume", redis.Z{
		Score:  float64(tick.AccVolume),
		Member: tick.Ticker,
	})

	_, err := pipe.Exec(ctx)
	if err != nil {
		log.Printf("Redis Tick Pipeline error for %s: %v", tick.Ticker, err)
	}
}

func (w *MarketDataWorker) updateOrderbookToRedis(ctx context.Context, ob Orderbook) {
	data, _ := json.Marshal(ob)
	// 호가창은 덮어쓰기 형태로 최신화
	err := w.redis.Set(ctx, "stocks:orderbook:"+ob.Ticker, data, 1*time.Hour).Err()
	if err != nil {
		log.Printf("Redis Orderbook error for %s: %v", ob.Ticker, err)
	}
}

// Wait graceful shutdown 시, wsClient.MessageChan 이 닫힌 뒤 워커가 잔여 큐를 모두 비울 때까지 차단(Block)한다.
func (w *MarketDataWorker) Wait() {
	w.wg.Wait()
}
