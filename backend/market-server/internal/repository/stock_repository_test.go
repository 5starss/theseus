package repository

import (
	"context"
	"fmt"
	"testing"

	"market-server/internal/domain"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
)

func newTestRepo(t *testing.T) (*StockRepository, *miniredis.Miniredis) {
	t.Helper()
	mr, err := miniredis.Run()
	if err != nil {
		t.Fatalf("miniredis start failed: %v", err)
	}
	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	return NewStockRepository(rdb, nil), mr
}

func TestBulkUpsertStocks_And_GetTopByVolume(t *testing.T) {
	repo, mr := newTestRepo(t)
	defer mr.Close()

	ctx := context.Background()

	stocks := []*domain.Stock{
		{Ticker: "005930", Name: "삼성전자", CurrentPrice: 70000, ChangeRate: 1.5, AccVolume: 3000000},
		{Ticker: "000660", Name: "SK하이닉스", CurrentPrice: 180000, ChangeRate: -0.5, AccVolume: 5000000},
		{Ticker: "035420", Name: "NAVER", CurrentPrice: 200000, ChangeRate: 0.8, AccVolume: 1000000},
	}

	if err := repo.BulkUpsertStocks(ctx, stocks); err != nil {
		t.Fatalf("BulkUpsertStocks failed: %v", err)
	}

	// 상위 2개 조회 — AccVolume 내림차순: SK하이닉스(5M) > 삼성전자(3M)
	result, err := repo.GetTopByVolume(ctx, 2)
	if err != nil {
		t.Fatalf("GetTopByVolume failed: %v", err)
	}
	if len(result) != 2 {
		t.Fatalf("expected 2 stocks, got %d", len(result))
	}
	if result[0].Ticker != "000660" {
		t.Errorf("expected 000660 at rank 1, got %s", result[0].Ticker)
	}
	if result[1].Ticker != "005930" {
		t.Errorf("expected 005930 at rank 2, got %s", result[1].Ticker)
	}
}

func TestGetTopByVolume_EmptySet(t *testing.T) {
	repo, mr := newTestRepo(t)
	defer mr.Close()

	result, err := repo.GetTopByVolume(context.Background(), 50)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(result) != 0 {
		t.Errorf("expected empty slice, got %d", len(result))
	}
}

func TestGetTopByVolume_SkipsMissingInfoKey(t *testing.T) {
	repo, mr := newTestRepo(t)
	defer mr.Close()

	ctx := context.Background()

	// Sorted Set에만 등록하고 info 키는 없는 종목
	mr.ZAdd(rankVolumeKey, 9999, "GHOST")

	// 정상 종목도 추가
	s := &domain.Stock{Ticker: "005930", Name: "삼성전자", CurrentPrice: 70000, AccVolume: 3000000}
	if err := repo.BulkUpsertStocks(ctx, []*domain.Stock{s}); err != nil {
		t.Fatalf("BulkUpsertStocks failed: %v", err)
	}

	result, err := repo.GetTopByVolume(ctx, 10)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	for _, stock := range result {
		if stock.Ticker == "GHOST" {
			t.Error("GHOST ticker should have been skipped due to missing info key")
		}
	}
}

// ─── Candle Cache Tests ────────────────────────────────────────────────────

func TestGetCandlesFromCache_Miss(t *testing.T) {
	repo, mr := newTestRepo(t)
	defer mr.Close()

	candles, err := repo.GetCandlesFromCache(context.Background(), "005930", "D")
	if err != nil {
		t.Fatalf("unexpected error on cache miss: %v", err)
	}
	if candles != nil {
		t.Errorf("expected nil on cache miss, got %v", candles)
	}
}

func TestSaveAndGetCandlesFromCache(t *testing.T) {
	repo, mr := newTestRepo(t)
	defer mr.Close()

	ctx := context.Background()
	original := []domain.Candle{
		{Timestamp: "20240101", Open: 70000, High: 71000, Low: 69000, Close: 70500, Volume: 1000000},
		{Timestamp: "20240102", Open: 70500, High: 72000, Low: 70000, Close: 71500, Volume: 1200000},
	}

	if err := repo.SaveCandlesToCache(ctx, "005930", "D", original); err != nil {
		t.Fatalf("SaveCandlesToCache failed: %v", err)
	}

	result, err := repo.GetCandlesFromCache(ctx, "005930", "D")
	if err != nil {
		t.Fatalf("GetCandlesFromCache failed: %v", err)
	}
	if len(result) != len(original) {
		t.Fatalf("expected %d candles, got %d", len(original), len(result))
	}
	if result[0].Timestamp != "20240101" || result[0].Close != 70500 || result[0].Volume != 1000000 {
		t.Errorf("candle data mismatch: %+v", result[0])
	}
	if result[1].Timestamp != "20240102" || result[1].High != 72000 {
		t.Errorf("candle data mismatch: %+v", result[1])
	}
}

func TestSaveAndGetCandlesFromCache_IntervalIsolation(t *testing.T) {
	repo, mr := newTestRepo(t)
	defer mr.Close()

	ctx := context.Background()
	daily := []domain.Candle{{Timestamp: "20240101", Volume: 1000000}}
	weekly := []domain.Candle{{Timestamp: "20240101", Volume: 5000000}}

	if err := repo.SaveCandlesToCache(ctx, "005930", "D", daily); err != nil {
		t.Fatalf("save daily failed: %v", err)
	}
	if err := repo.SaveCandlesToCache(ctx, "005930", "W", weekly); err != nil {
		t.Fatalf("save weekly failed: %v", err)
	}

	gotD, err := repo.GetCandlesFromCache(ctx, "005930", "D")
	if err != nil {
		t.Fatalf("get daily failed: %v", err)
	}
	gotW, err := repo.GetCandlesFromCache(ctx, "005930", "W")
	if err != nil {
		t.Fatalf("get weekly failed: %v", err)
	}

	if gotD[0].Volume != 1000000 {
		t.Errorf("expected daily volume 1000000, got %d", gotD[0].Volume)
	}
	if gotW[0].Volume != 5000000 {
		t.Errorf("expected weekly volume 5000000, got %d", gotW[0].Volume)
	}
}

func TestSaveAndGetCandlesFromCache_TickerIsolation(t *testing.T) {
	repo, mr := newTestRepo(t)
	defer mr.Close()

	ctx := context.Background()
	samsung := []domain.Candle{{Timestamp: "20240101", Close: 70500}}
	skhynix := []domain.Candle{{Timestamp: "20240101", Close: 181000}}

	_ = repo.SaveCandlesToCache(ctx, "005930", "D", samsung)
	_ = repo.SaveCandlesToCache(ctx, "000660", "D", skhynix)

	gotS, _ := repo.GetCandlesFromCache(ctx, "005930", "D")
	gotH, _ := repo.GetCandlesFromCache(ctx, "000660", "D")

	if gotS[0].Close != 70500 {
		t.Errorf("expected samsung close 70500, got %d", gotS[0].Close)
	}
	if gotH[0].Close != 181000 {
		t.Errorf("expected skhynix close 181000, got %d", gotH[0].Close)
	}
}

// ─── Stock Data Integrity ────────────────────────────────────────────────────

func TestBulkUpsertStocks_DataIntegrity(t *testing.T) {
	repo, mr := newTestRepo(t)
	defer mr.Close()

	ctx := context.Background()
	original := &domain.Stock{
		Ticker:       "035720",
		Name:         "카카오",
		CurrentPrice: 45000,
		ChangeRate:   2.3,
		AccVolume:    2500000,
	}

	if err := repo.BulkUpsertStocks(ctx, []*domain.Stock{original}); err != nil {
		t.Fatalf("BulkUpsertStocks failed: %v", err)
	}

	// Redis에서 직접 Hash를 읽어 필드 정합성 확인
	key := fmt.Sprintf(stockInfoKeyFmt, original.Ticker)
	name := mr.HGet(key, "name")
	if name == "" {
		t.Fatalf("key not found in redis")
	}
	cpStr := mr.HGet(key, "currentPrice")
	
	if name != original.Name || cpStr != "45000" {
		t.Errorf("data mismatch: want Name=%s CurrentPrice=45000, got Name=%s CurrentPrice=%s", original.Name, name, cpStr)
	}
}
