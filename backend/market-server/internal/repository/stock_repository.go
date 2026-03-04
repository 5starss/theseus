package repository

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"market-server/internal/domain"

	"github.com/redis/go-redis/v9"
)

const (
	rankVolumeKey   = "stocks:rank:volume" // Sorted Set: score=거래량, member=종목코드
	stockInfoKeyFmt = "stocks:info:%s"     // String: JSON 직렬화된 Stock
)

type StockRepository struct {
	rdb *redis.Client
}

func NewStockRepository(rdb *redis.Client) *StockRepository {
	return &StockRepository{rdb: rdb}
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

	// 2단계: Pipeline으로 종목 상세정보 일괄 조회
	pipe := r.rdb.Pipeline()
	cmds := make([]*redis.StringCmd, len(tickers))
	for i, ticker := range tickers {
		cmds[i] = pipe.Get(ctx, fmt.Sprintf(stockInfoKeyFmt, ticker))
	}
	if _, err := pipe.Exec(ctx); err != nil && err != redis.Nil {
		return nil, fmt.Errorf("pipeline exec failed: %w", err)
	}

	stocks := make([]*domain.Stock, 0, len(tickers))
	for _, cmd := range cmds {
		val, err := cmd.Result()
		if err != nil {
			continue // 개별 키 누락은 건너뜀
		}
		var s domain.Stock
		if err := json.Unmarshal([]byte(val), &s); err != nil {
			continue
		}
		stocks = append(stocks, &s)
	}

	return stocks, nil
}

// BulkUpsertStocks Pipeline으로 종목 정보와 거래량 순위를 일괄 저장한다.
// stocks:info:{ticker} ← JSON, stocks:rank:volume ← ZADD score=거래량
func (r *StockRepository) BulkUpsertStocks(ctx context.Context, stocks []*domain.Stock) error {
	pipe := r.rdb.Pipeline()

	for _, s := range stocks {
		data, err := json.Marshal(s)
		if err != nil {
			return fmt.Errorf("marshal failed for %s: %w", s.Ticker, err)
		}
		key := fmt.Sprintf(stockInfoKeyFmt, s.Ticker)
		pipe.Set(ctx, key, data, 24*time.Hour)
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
