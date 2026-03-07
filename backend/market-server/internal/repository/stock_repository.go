package repository

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strconv"
	"time"

	"market-server/internal/domain"

	"github.com/redis/go-redis/v9"
)

const (
	rankVolumeKey   = "stocks:rank:volume"   // Sorted Set: score=거래량, member=종목코드
	stockInfoKeyFmt = "stocks:info:%s"       // Hash: 종목 상세 정보
	candlesKeyFmt   = "stocks:candles:%s:%s" // String (JSON): 캔들 데이터 단기 캐시 (ticker, interval)
)

type StockRepository struct {
	rdb *redis.Client
	db  *sql.DB
}

func NewStockRepository(rdb *redis.Client, db *sql.DB) *StockRepository {
	return &StockRepository{rdb: rdb, db: db}
}

// GetTopByVolume Redis Sorted Set에서 거래량 상위 limit개 종목을 조회한다.
// ZREVRANGE → Pipeline MGET 순서로 두 번의 왕복으로 처리한다.
func (r *StockRepository) GetTopByVolume(ctx context.Context, limit int64) ([]*domain.Stock, error) {
	// 1단계: Sorted Set에서 상위 종목코드 목록 조회 (내림차순)
	tickers, err := r.rdb.ZRevRange(ctx, rankVolumeKey, 0, limit-1).Result()
	if err != nil {
		return nil, fmt.Errorf("zrevrange failed: %w", err)
	}
	if len(tickers) == 0 {
		return []*domain.Stock{}, nil
	}

	// 2단계: Pipeline으로 종목 상세정보 일괄 조회 (HGETALL)
	pipe := r.rdb.Pipeline()
	cmds := make([]*redis.MapStringStringCmd, len(tickers))
	for i, ticker := range tickers {
		cmds[i] = pipe.HGetAll(ctx, fmt.Sprintf(stockInfoKeyFmt, ticker))
	}
	if _, err := pipe.Exec(ctx); err != nil && err != redis.Nil {
		return nil, fmt.Errorf("pipeline exec failed: %w", err)
	}

	stocks := make([]*domain.Stock, 0, len(tickers))
	for _, cmd := range cmds {
		val, err := cmd.Result()
		if err != nil || len(val) == 0 {
			continue // 개별 키 누락은 건너뜀
		}
		
		// Map을 파싱하여 Stock 객체로 변환
		currentPrice, _ := strconv.ParseInt(val["currentPrice"], 10, 64)
		changeRate, _ := strconv.ParseFloat(val["changeRate"], 64)
		accVolume, _ := strconv.ParseInt(val["accVolume"], 10, 64)

		stocks = append(stocks, &domain.Stock{
			Ticker:       val["ticker"],
			Name:         val["name"],
			CurrentPrice: currentPrice,
			ChangeRate:   changeRate,
			AccVolume:    accVolume,
		})
	}

	return stocks, nil
}

// BulkUpsertStocks Pipeline으로 종목 정보와 거래량 순위를 일괄 저장한다.
// stocks:info:{ticker} ← Hash, stocks:rank:volume ← ZADD score=거래량
func (r *StockRepository) BulkUpsertStocks(ctx context.Context, stocks []*domain.Stock) error {
	pipe := r.rdb.Pipeline()

	for _, s := range stocks {
		key := fmt.Sprintf(stockInfoKeyFmt, s.Ticker)
		pipe.HSet(ctx, key, map[string]interface{}{
			"ticker":       s.Ticker,
			"name":         s.Name,
			"currentPrice": s.CurrentPrice,
			"changeRate":   s.ChangeRate,
			"accVolume":    s.AccVolume,
		})
		pipe.Expire(ctx, key, 24*time.Hour)
		pipe.ZAdd(ctx, rankVolumeKey, redis.Z{
			Score:  float64(s.AccVolume),
			Member: s.Ticker,
		})
	}

	if _, err := pipe.Exec(ctx); err != nil {
		return fmt.Errorf("bulk upsert pipeline exec failed: %w", err)
	}

	return nil
}

// GetCandlesFromCache Redis에서 캔들 데이터를 단기 캐시로 조회한다.
func (r *StockRepository) GetCandlesFromCache(ctx context.Context, ticker string, interval string) ([]domain.Candle, error) {
	key := fmt.Sprintf(candlesKeyFmt, ticker, interval)
	val, err := r.rdb.Get(ctx, key).Result()
	if err == redis.Nil {
		return nil, nil // Cache Miss
	} else if err != nil {
		return nil, fmt.Errorf("redis get failed: %w", err)
	}

	var candles []domain.Candle
	if err := json.Unmarshal([]byte(val), &candles); err != nil {
		return nil, fmt.Errorf("json unmarshal failed: %w", err)
	}
	return candles, nil
}

// SaveCandlesToCache Redis에 캔들 데이터를 적재시킨다. (TTL: 1분)
func (r *StockRepository) SaveCandlesToCache(ctx context.Context, ticker string, interval string, candles []domain.Candle) error {
	key := fmt.Sprintf(candlesKeyFmt, ticker, interval)
	
	bytes, err := json.Marshal(candles)
	if err != nil {
		return fmt.Errorf("json marshal failed: %w", err)
	}

	if err := r.rdb.Set(ctx, key, string(bytes), 1*time.Minute).Err(); err != nil {
		return fmt.Errorf("redis set failed: %w", err)
	}
	return nil
}

// GetCandlesFromDB MySQL에서 캔들 데이터를 조회한다.
func (r *StockRepository) GetCandlesFromDB(ctx context.Context, ticker string, interval string, limit int64) ([]domain.Candle, error) {
	query := `
		SELECT timestamp, open, high, low, close, volume
		FROM candles
		WHERE ticker = ? AND interval_type = ?
		ORDER BY timestamp DESC
		LIMIT ?
	`
	rows, err := r.db.QueryContext(ctx, query, ticker, interval, limit)
	if err != nil {
		return nil, fmt.Errorf("mysql query failed: %w", err)
	}
	defer rows.Close()

	var candles []domain.Candle
	for rows.Next() {
		var c domain.Candle
		var ts string
		
		if err := rows.Scan(&ts, &c.Open, &c.High, &c.Low, &c.Close, &c.Volume); err != nil {
			return nil, fmt.Errorf("rows scan failed: %w", err)
		}
		c.Timestamp = ts
		candles = append(candles, c)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration failed: %w", err)
	}

	return candles, nil
}

// GetOrderbookSnapshot Redis에서 호가창 스냅샷 및 현재가 정보를 조회하여 반환한다.
func (r *StockRepository) GetOrderbookSnapshot(ctx context.Context, ticker string) (*domain.OrderbookResponse, error) {
	// 조회할 키
	orderbookKey := "stocks:orderbook:" + ticker
	currentKey := "stocks:current:" + ticker

	// 1. Pipeline을 통한 동시 조회
	pipe := r.rdb.Pipeline()
	obCmd := pipe.Get(ctx, orderbookKey)
	currCmd := pipe.HGetAll(ctx, currentKey)

	_, err := pipe.Exec(ctx)
	if err != nil && err != redis.Nil {
		return nil, fmt.Errorf("pipeline exec failed: %w", err)
	}

	obJSON, err := obCmd.Result()
	if err == redis.Nil {
		return nil, nil // 호가 데이터 없음
	} else if err != nil {
		return nil, fmt.Errorf("redis get orderbook failed: %w", err)
	}

	currHash, err := currCmd.Result()
	if err != nil && err != redis.Nil {
		return nil, fmt.Errorf("redis hgetall current failed: %w", err)
	}

	// 2. 파싱 및 병합
	var resp domain.OrderbookResponse
	if err := json.Unmarshal([]byte(obJSON), &resp); err != nil {
		return nil, fmt.Errorf("json unmarshal orderbook failed: %w", err)
	}

	// current가 존재하면 덮어쓰기 (워커가 저장한 실시간 체결가)
	if len(currHash) > 0 {
		if p, err := strconv.ParseFloat(currHash["price"], 64); err == nil {
			resp.CurrentPrice = p
		}
		if cr, err := strconv.ParseFloat(currHash["change_rate"], 64); err == nil {
			resp.ChangeRate = cr
		}
	} else {
		// Fallback: stocks:info:{ticker} 조회 
		infoCmd := r.rdb.HGetAll(ctx, fmt.Sprintf(stockInfoKeyFmt, ticker))
		infoHash, err := infoCmd.Result()
		if err == nil && len(infoHash) > 0 {
			if p, err := strconv.ParseFloat(infoHash["currentPrice"], 64); err == nil {
				resp.CurrentPrice = p
			}
			if cr, err := strconv.ParseFloat(infoHash["changeRate"], 64); err == nil {
				resp.ChangeRate = cr
			}
		}
	}

	return &resp, nil
}
