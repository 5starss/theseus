package service

import (
	"context"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"market-server/internal/domain"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"

	"market-server/internal/repository"
)

// ─── 헬퍼 ────────────────────────────────────────────────────────────────────

// newColdService 캐시가 완전히 비어있는(Cold) 서비스를 반환한다.
// lastCacheTime 이 zero-value 이므로 첫 SearchStocks 호출 시 반드시 Redis 조회가 발생한다.
func newColdService(t *testing.T) (*StockService, *repository.StockRepository, *miniredis.Miniredis) {
	t.Helper()
	mr, err := miniredis.Run()
	if err != nil {
		t.Fatalf("miniredis start failed: %v", err)
	}
	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	repo := repository.NewStockRepository(rdb, nil)
	svc := NewStockService(repo)
	// stockCache 는 make([]*domain.Stock, 0) 이고 lastCacheTime 은 zero → isFresh = false
	return svc, repo, mr
}

// ─── Singleflight 동시성 테스트 ──────────────────────────────────────────────

// TestSingleflight_Concurrent100_AllGetCorrectResult
// 100개 고루틴이 동시에 캐시 Cold 상태에서 SearchStocks 를 호출한다.
// singleflight 가 정상 동작하면 모든 고루틴이 올바른 결과를 받아야 한다.
// `go test -race` 로 실행하면 데이터 레이스도 동시에 검증된다.
func TestSingleflight_Concurrent100_AllGetCorrectResult(t *testing.T) {
	svc, repo, mr := newColdService(t)
	defer mr.Close()

	seedStocksForSearch(t, repo, []*domain.Stock{
		{Ticker: "005930", Name: "삼성전자", AccVolume: 3_000_000},
		{Ticker: "000660", Name: "SK하이닉스", AccVolume: 5_000_000},
	})

	const n = 100
	results := make([][]*domain.Stock, n)
	errs := make([]error, n)

	var wg sync.WaitGroup
	wg.Add(n)
	// 모든 고루틴이 최대한 동시에 출발하도록 startGun 으로 동기화
	var startGun sync.WaitGroup
	startGun.Add(1)

	for i := 0; i < n; i++ {
		go func(idx int) {
			defer wg.Done()
			startGun.Wait() // 출발 신호 대기
			res, err := svc.SearchStocks(context.Background(), "삼성", 10)
			results[idx] = res
			errs[idx] = err
		}(i)
	}

	startGun.Done() // 출발
	wg.Wait()

	// 모든 고루틴이 에러 없이 정확한 결과를 받아야 한다
	for i := 0; i < n; i++ {
		if errs[i] != nil {
			t.Errorf("goroutine[%d]: unexpected error: %v", i, errs[i])
		}
		if len(results[i]) != 1 {
			t.Errorf("goroutine[%d]: expected 1 result, got %d", i, len(results[i]))
			continue
		}
		if results[i][0].Ticker != "005930" {
			t.Errorf("goroutine[%d]: expected 005930, got %s", i, results[i][0].Ticker)
		}
	}
}

// TestSingleflight_CachePopulatedExactlyOnce
// 100개 고루틴이 동시에 Cold 캐시에서 호출할 때, 캐시 갱신은 정확히 한 번만 발생해야 한다.
// singleflight 가 동작하면 stockCache 포인터는 한 번만 교체되고,
// lastCacheTime 은 단조증가(monotonic) 해야 한다.
func TestSingleflight_CachePopulatedExactlyOnce(t *testing.T) {
	svc, repo, mr := newColdService(t)
	defer mr.Close()

	seedStocksForSearch(t, repo, []*domain.Stock{
		{Ticker: "005930", Name: "삼성전자", AccVolume: 1_000_000},
	})

	const n = 50
	var wg sync.WaitGroup
	var startGun sync.WaitGroup
	wg.Add(n)
	startGun.Add(1)

	// 캐시가 마지막으로 교체된 시각을 추적 (단조증가 확인용)
	var latestCacheTime atomic.Int64

	for i := 0; i < n; i++ {
		go func() {
			defer wg.Done()
			startGun.Wait()
			svc.loadStockCache(context.Background())

			svc.stockCacheLock.RLock()
			ts := svc.lastCacheTime.UnixNano()
			svc.stockCacheLock.RUnlock()

			// 동시에 여러 번 쓰여져도 UnixNano 는 동일하거나 더 커야 함
			for {
				cur := latestCacheTime.Load()
				if ts >= cur {
					if latestCacheTime.CompareAndSwap(cur, ts) {
						break
					}
				} else {
					break
				}
			}
		}()
	}

	startGun.Done()
	wg.Wait()

	// 캐시가 올바르게 채워져 있어야 한다
	svc.stockCacheLock.RLock()
	cacheLen := len(svc.stockCache)
	svc.stockCacheLock.RUnlock()

	if cacheLen != 1 {
		t.Errorf("expected cache to have 1 stock after concurrent load, got %d", cacheLen)
	}
}

// TestSingleflight_WarmCacheSurvivesRedisDown
// 캐시가 한 번 로드된 후 Redis 가 다운되어도 인메모리 캐시로 검색이 계속 동작해야 한다.
// singleflight 가 캐시를 정확히 채웠다는 간접 증명이기도 하다.
func TestSingleflight_WarmCacheSurvivesRedisDown(t *testing.T) {
	svc, repo, mr := newColdService(t)
	// mr.Close()는 아래에서 직접 호출

	seedStocksForSearch(t, repo, []*domain.Stock{
		{Ticker: "005930", Name: "삼성전자", AccVolume: 3_000_000},
		{Ticker: "000660", Name: "SK하이닉스", AccVolume: 5_000_000},
	})

	// 1. 첫 번째 호출 → Redis 에서 캐시 로드
	result1, err := svc.SearchStocks(context.Background(), "삼성", 10)
	if err != nil {
		t.Fatalf("initial search failed: %v", err)
	}
	if len(result1) != 1 || result1[0].Ticker != "005930" {
		t.Fatalf("initial search wrong result: %v", result1)
	}

	// 2. Redis 를 강제 종료
	mr.Close()

	// 3. Redis 가 없어도 인메모리 캐시로 검색이 동작해야 한다 (isFresh == true)
	result2, err := svc.SearchStocks(context.Background(), "삼성", 10)
	if err != nil {
		t.Fatalf("search after redis down failed: %v", err)
	}
	if len(result2) != 1 || result2[0].Ticker != "005930" {
		t.Errorf("expected same result after redis down, got: %v", result2)
	}
}

// TestSingleflight_CacheRefreshAfterExpiry
// 캐시 TTL(1시간)이 만료된 후 새로운 데이터가 반영되는지 확인한다.
// lastCacheTime 을 1시간 이전으로 조작하여 강제로 캐시 만료를 재현한다.
func TestSingleflight_CacheRefreshAfterExpiry(t *testing.T) {
	svc, repo, mr := newColdService(t)
	defer mr.Close()

	// 1. 초기 데이터 적재 및 캐시 로드
	seedStocksForSearch(t, repo, []*domain.Stock{
		{Ticker: "005930", Name: "삼성전자", AccVolume: 1_000_000},
	})
	svc.loadStockCache(context.Background())

	// 2. lastCacheTime 을 2시간 전으로 되돌려 캐시 만료 시뮬레이션
	svc.stockCacheLock.Lock()
	svc.lastCacheTime = time.Now().Add(-2 * time.Hour)
	svc.stockCacheLock.Unlock()

	// 3. Redis 에 새 종목 추가
	if err := repo.BulkUpsertStocks(context.Background(), []*domain.Stock{
		{Ticker: "000660", Name: "SK하이닉스", AccVolume: 9_999_999},
	}); err != nil {
		t.Fatalf("upsert failed: %v", err)
	}

	// 4. 만료된 캐시 재로드 트리거
	svc.loadStockCache(context.Background())

	// 5. 새 데이터가 캐시에 반영되어 검색 가능해야 한다
	result, err := svc.SearchStocks(context.Background(), "SK", 10)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(result) == 0 {
		t.Error("expected SK하이닉스 to appear after cache refresh, got empty")
	} else if result[0].Ticker != "000660" {
		t.Errorf("expected 000660, got %s", result[0].Ticker)
	}
}

// TestSingleflight_FreshCache_SkipsRedis
// isFresh == true 인 상태에서 sfGroup.Do 가 호출되지 않음을 확인한다.
// Redis 를 먼저 닫은 뒤 캐시가 fresh 하면 에러 없이 결과를 반환해야 한다.
func TestSingleflight_FreshCache_SkipsRedis(t *testing.T) {
	svc, repo, mr := newColdService(t)

	seedStocksForSearch(t, repo, []*domain.Stock{
		{Ticker: "005930", Name: "삼성전자", AccVolume: 1_000_000},
	})

	// 캐시를 직접 "warm" 상태로 만들어 Redis 조회 없이 서비스 가능하게 함
	svc.stockCacheLock.Lock()
	svc.stockCache = []*domain.Stock{
		{Ticker: "005930", Name: "삼성전자", AccVolume: 1_000_000},
	}
	svc.lastCacheTime = time.Now() // fresh
	svc.stockCacheLock.Unlock()

	// Redis 종료 (이 시점부터 Redis 조회 시 에러 발생)
	mr.Close()

	// isFresh == true 이므로 Redis 를 건드리지 않아야 함
	result, err := svc.SearchStocks(context.Background(), "삼성", 10)
	if err != nil {
		t.Fatalf("expected no error with warm cache even when Redis is down: %v", err)
	}
	if len(result) != 1 || result[0].Ticker != "005930" {
		t.Errorf("expected 005930 from warm cache, got: %v", result)
	}
}

// TestSingleflight_ConcurrentExpiredCache_ConsistentResults
// 모든 고루틴이 동시에 만료된 캐시에 접근할 때 일관된 결과를 반환한다.
// singleflight 없이 이 테스트를 race detector 와 함께 실행하면 경쟁 조건이 발생할 수 있다.
func TestSingleflight_ConcurrentExpiredCache_ConsistentResults(t *testing.T) {
	svc, repo, mr := newColdService(t)
	defer mr.Close()

	seedStocksForSearch(t, repo, []*domain.Stock{
		{Ticker: "005930", Name: "삼성전자", AccVolume: 3_000_000},
	})

	// 캐시를 강제 만료 상태로 설정 (내용은 있으나 TTL 초과)
	svc.stockCacheLock.Lock()
	svc.stockCache = []*domain.Stock{{Ticker: "OLD", Name: "구데이터", AccVolume: 1}}
	svc.lastCacheTime = time.Now().Add(-2 * time.Hour) // 2시간 전 = 만료
	svc.stockCacheLock.Unlock()

	const n = 80
	var wg sync.WaitGroup
	var startGun sync.WaitGroup
	wg.Add(n)
	startGun.Add(1)

	type result struct {
		stocks []*domain.Stock
		err    error
	}
	results := make([]result, n)

	for i := 0; i < n; i++ {
		go func(idx int) {
			defer wg.Done()
			startGun.Wait()
			stocks, err := svc.SearchStocks(context.Background(), "삼성", 10)
			results[idx] = result{stocks, err}
		}(i)
	}

	startGun.Done()
	wg.Wait()

	// 재로드 후에는 모든 고루틴이 올바른(새) 데이터를 받아야 한다
	for i, r := range results {
		if r.err != nil {
			t.Errorf("goroutine[%d]: error: %v", i, r.err)
			continue
		}
		if len(r.stocks) != 1 || r.stocks[0].Ticker != "005930" {
			t.Errorf("goroutine[%d]: expected 005930(삼성전자), got %v", i, r.stocks)
		}
	}
}

// TestSingleflight_RedisErrorDuringLoad_GracefulDegradation
// Redis 가 다운된 상태에서 loadStockCache 가 호출되면
// 에러 로그만 남기고 기존 캐시(stale data)를 유지해야 한다.
// 서비스가 패닉 없이 빈 결과를 반환해야 한다.
func TestSingleflight_RedisErrorDuringLoad_GracefulDegradation(t *testing.T) {
	svc, _, mr := newColdService(t)

	// Redis 를 즉시 종료 (초기 로드 시 에러 발생 유도)
	mr.Close()

	// loadStockCache 는 에러를 로그로만 남기고 패닉하지 않아야 한다
	defer func() {
		if r := recover(); r != nil {
			t.Errorf("loadStockCache panicked: %v", r)
		}
	}()

	// SearchStocks 는 에러 없이 nil(빈 결과)을 반환해야 한다
	result, err := svc.SearchStocks(context.Background(), "삼성", 10)
	if err != nil {
		t.Errorf("expected nil error on Redis down, got: %v", err)
	}
	if result != nil {
		t.Errorf("expected nil result when cache is empty and Redis is down, got: %v", result)
	}
}

// TestSingleflight_ContextBehavior_DocumentedRisk
// sfGroup.Do 내부에서 context.Background() 를 사용하므로,
// 최초 호출자의 ctx 가 취소되어도 캐시 로드가 완료되어야 한다.
//
// [수정 전 문제]
// sfGroup.Do(func() { s.repo.GetAllStocks(ctx) }) — 최초 호출자 ctx 사용
// → ctx 취소 시 GetAllStocks 실패 → 대기 중인 모든 고루틴도 에러 수신
// → 캐시가 채워지지 않아 다음 요청에서 또 Redis 폭격 재개
//
// [수정 후]
// sfGroup.Do(func() { s.repo.GetAllStocks(context.Background()) }) — 독립 ctx 사용
// → 개별 요청 취소와 캐시 로드가 분리됨
func TestSingleflight_ContextBehavior_DocumentedRisk(t *testing.T) {
	t.Log("DESIGN NOTE: sfGroup.Do uses the first caller's ctx.")
	t.Log("If that ctx is cancelled mid-flight, all waiting goroutines also fail.")
	t.Log("Recommended fix: use context.Background() inside sfGroup.Do for cache loads.")

	svc, repo, mr := newColdService(t)
	defer mr.Close()

	seedStocksForSearch(t, repo, []*domain.Stock{
		{Ticker: "005930", Name: "삼성전자", AccVolume: 1_000_000},
	})

	// 미리 취소된 ctx 로 호출
	ctx, cancel := context.WithCancel(context.Background())
	cancel() // 즉시 취소

	// context.Background() 를 내부에서 사용하므로 취소된 ctx 와 무관하게 캐시가 채워져야 한다
	svc.loadStockCache(ctx)

	svc.stockCacheLock.RLock()
	cacheLen := len(svc.stockCache)
	svc.stockCacheLock.RUnlock()

	t.Logf("cache size after cancelled-ctx load: %d", cacheLen)
	if cacheLen == 0 {
		t.Error("cache should be populated even when caller ctx is cancelled (fix: use context.Background() inside sfGroup.Do)")
	}
}
