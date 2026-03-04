package service

import (
	"context"
	"log"
	"time"

	"market-server/internal/domain"
	"market-server/internal/repository"
	"market-server/pkg/kis"
)

type StockService struct {
	repo      *repository.StockRepository
	kisClient *kis.Client
}

func NewStockService(repo *repository.StockRepository, kisClient *kis.Client) *StockService {
	return &StockService{
		repo:      repo,
		kisClient: kisClient,
	}
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

// refreshRanking KIS OpenAPI에서 거래량 순위를 가져와 Redis에 갱신한다.
// 실패 시 로그만 남기고 기존 Redis 데이터를 유지한다.
func (s *StockService) refreshRanking(ctx context.Context, limit int) {
	stocks, err := s.kisClient.GetVolumeRanking(ctx, limit)
	if err != nil {
		log.Printf("[StockService] KIS volume ranking fetch failed: %v", err)
		return
	}

	if err := s.repo.BulkUpsertStocks(ctx, stocks); err != nil {
		log.Printf("[StockService] Redis bulk upsert failed: %v", err)
		return
	}

	log.Printf("[StockService] Ranking refreshed: %d stocks updated", len(stocks))
}

// StartRankingScheduler 백그라운드 goroutine에서 interval 주기로 순위를 갱신한다.
// 서버 시작 즉시 1회 실행 후 Ticker로 반복하며, ctx 취소 시 graceful하게 종료한다.
func (s *StockService) StartRankingScheduler(ctx context.Context, interval time.Duration) {
	go func() {
		s.refreshRanking(ctx, 50) // 초기 데이터 즉시 적재

		ticker := time.NewTicker(interval)
		defer ticker.Stop()

		for {
			select {
			case <-ticker.C:
				s.refreshRanking(ctx, 50)
			case <-ctx.Done():
				log.Println("[StockService] Ranking scheduler stopped")
				return
			}
		}
	}()
}
