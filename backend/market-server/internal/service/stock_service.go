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
func (s *StockService) GetCandles(ctx context.Context, ticker string, interval domain.Interval, limit int64, endTime string) ([]domain.Candle, error) {
	// 최신 데이터 조회가 아닐 경우 (커서 페이징 - 이전 데이터 조회)
	if endTime != "" {
		// 과거 데이터는 자주 변하지 않고 온전한 상태로 DB에만 의존해서 가져온다고 가정
		// ZSet 캐시를 사용하도록 repository가 변경되면 여기서 그냥 찔러도 무방하게 바뀜
		candles, err := s.repo.GetCandlesFromDB(ctx, ticker, interval, limit, endTime)
		if err != nil {
			return nil, fmt.Errorf("historical db fetch error: %w", err)
		}
		return candles, nil
	}

	// 1. 최신 데이터 조회 진행 (endTime == "")
	// Redis 캐시 조회 (DB 데이터 캐싱 부분)
	candles, err := s.repo.GetCandlesFromCache(ctx, ticker, interval)
	if err != nil {
		log.Printf("[StockService] Cache read error for %s (%s): %v", ticker, interval, err)
	}

	// 2. Cache Miss: DB 조회
	if len(candles) == 0 {
		candles, err = s.repo.GetCandlesFromDB(ctx, ticker, interval, limit, "") // endTime 빈 문자열 전달
		if err != nil {
			return nil, fmt.Errorf("db fetch error: %w", err)
		}

		// 3. 비동기로 Redis 캐시에 DB 결과 저장
		if len(candles) > 0 {
			go func(c []domain.Candle) {
				bgCtx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
				defer cancel()
				if err := s.repo.SaveCandlesToCache(bgCtx, ticker, interval, c); err != nil {
					log.Printf("[StockService] Failed to cache candles for %s: %v", ticker, err)
				}
			}(candles)
		}
	}

	// 4. interval이 domain.IntervalDay 일 경우, 실시간(오늘자) 캔들을 최상단에 추가 (On-the-fly)
	if interval == domain.IntervalDay {
		liveSnap, err := s.repo.GetTickSnapshot(ctx, ticker)
		if err == nil && liveSnap != nil && liveSnap.CurrentPrice > 0 {
			todayStr := time.Now().Format("2006-01-02")
			
			// DB에 이미 오늘자 캔들이 있는지 확인하고, 있으면 덮어쓰거나, 없으면 맨 앞에 추가
			hasToday := false
			if len(candles) > 0 && candles[0].Timestamp == todayStr {
				hasToday = true
			}

			liveCandle := domain.Candle{
				Timestamp: todayStr,
				Open:      int64(liveSnap.OpenPrice),
				High:      int64(liveSnap.HighPrice),
				Low:       int64(liveSnap.LowPrice),
				Close:     int64(liveSnap.CurrentPrice),
				Volume:    liveSnap.AccVolume,
			}

			if hasToday {
				candles[0] = liveCandle
			} else {
				// 맨 앞에 prepend
				candles = append([]domain.Candle{liveCandle}, candles...)
				if limit > 0 && int64(len(candles)) > limit {
					candles = candles[:limit]
				}
			}
		}
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
