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
	return NewStockRepository(rdb), mr
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
