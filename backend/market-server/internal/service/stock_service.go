package service

import (
	"context"
	"fmt"
	"log"
	"time"

	"market-server/internal/domain"
	"market-server/internal/repository"
)

type StockService struct {
	repo *repository.StockRepository
}

func NewStockService(repo *repository.StockRepository) *StockService {
	return &StockService{repo: repo}
}

// GetTopStocks rankType 기준 상위 limit개 종목을 Redis에서 조회한다.
func (s *StockService) GetTopStocks(ctx context.Context, limit int64, rankType domain.RankType) ([]*domain.Stock, error) {
	switch rankType {
	case domain.RankTypeVolume:
		return s.repo.GetTopByVolume(ctx, limit)
	default:
		return s.repo.GetTopByVolume(ctx, limit)
	}
}

// GetCandles 종목의 캔들 데이터를 Cache-Aside 패턴으로 조회한다.
func (s *StockService) GetCandles(ctx context.Context, ticker string, interval string, limit int64) ([]domain.Candle, error) {
	// 1. Redis 캐시 조회
	candles, err := s.repo.GetCandlesFromCache(ctx, ticker, interval)
	if err != nil {
		log.Printf("[StockService] Cache read error for %s (%s): %v", ticker, interval, err)
	}
	// Cache Hit
	if len(candles) > 0 {
		return candles, nil
	}

	// 2. Cache Miss: DB 조회
	candles, err = s.repo.GetCandlesFromDB(ctx, ticker, interval, limit)
	if err != nil {
		return nil, fmt.Errorf("db fetch error: %w", err)
	}

	// 3. 비동기로 Redis 캐시에 저장
	if len(candles) > 0 {
		go func(c []domain.Candle) {
			bgCtx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
			defer cancel()
			if err := s.repo.SaveCandlesToCache(bgCtx, ticker, interval, c); err != nil {
				log.Printf("[StockService] Failed to cache candles for %s: %v", ticker, err)
			}
		}(candles)
	}

	return candles, nil
}

// GetOrderbook 호가창 스냅샷 및 현재가 정보를 조회한다.
func (s *StockService) GetOrderbook(ctx context.Context, ticker string) (*domain.OrderbookResponse, error) {
	ob, err := s.repo.GetOrderbookSnapshot(ctx, ticker)
	if err != nil {
		return nil, fmt.Errorf("repository get orderbook snapshot error: %w", err)
	}
	return ob, nil
}

// GetTickSnapshot 상세 종목 실시간 체결 스냅샷 정보를 조회한다.
func (s *StockService) GetTickSnapshot(ctx context.Context, ticker string) (*domain.TickSnapshotResponse, error) {
	snap, err := s.repo.GetTickSnapshot(ctx, ticker)
	if err != nil {
		return nil, fmt.Errorf("repository get tick snapshot error: %w", err)
	}
	return snap, nil
}
