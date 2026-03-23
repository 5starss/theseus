package service

import (
	"context"
	"testing"

	"market-server/internal/domain"
	"market-server/internal/repository"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
)

// newTestService miniredis 기반 서비스 인스턴스를 생성한다.
// KIS 클라이언트는 nil로 설정 — GetCandles/GetTopStocks에는 사용되지 않는다.
func newTestService(t *testing.T) (*StockService, *repository.StockRepository, *miniredis.Miniredis) {
	t.Helper()
	mr, err := miniredis.Run()
	if err != nil {
		t.Fatalf("miniredis start failed: %v", err)
	}
	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	repo := repository.NewStockRepository(rdb, nil)
	return NewStockService(repo), repo, mr
}

// seedCandleCache ZSet 기반 캔들 캐시에 테스트 데이터를 적재한다.
// Timestamp 포맷은 IntervalDay: "2006-01-02", IntervalMinute: "2006-01-02 15:04:05" 이어야 한다.
func seedCandleCache(t *testing.T, repo *repository.StockRepository, ticker string, interval domain.Interval, candles []domain.Candle) {
	t.Helper()
	if err := repo.SaveCandlesToCache(context.Background(), ticker, interval, candles); err != nil {
		t.Fatalf("seedCandleCache failed: %v", err)
	}
}

// ─── GetCandles 테스트 ────────────────────────────────────────────────────────

func TestGetCandles_CacheHit(t *testing.T) {
	svc, repo, mr := newTestService(t)
	defer mr.Close()

	// ZSet score 계산을 위해 MySQL DATE 포맷("2006-01-02") 사용
	candles := []domain.Candle{
		{Timestamp: "2024-01-01", Open: 70000, High: 71000, Low: 69000, Close: 70500, Volume: 1000000},
		{Timestamp: "2024-01-02", Open: 70500, High: 72000, Low: 70000, Close: 71500, Volume: 1200000},
	}
	seedCandleCache(t, repo, "005930", domain.IntervalDay, candles)

	got, err := svc.GetCandles(context.Background(), "005930", domain.IntervalDay, 50, "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 2 {
		t.Fatalf("expected 2 candles, got %d", len(got))
	}
	// ZRevRange로 조회하므로 최신(2024-01-02)이 먼저 반환된다
	if got[0].Timestamp != "2024-01-02" || got[0].Close != 71500 {
		t.Errorf("first candle mismatch: %+v", got[0])
	}
	if got[1].Timestamp != "2024-01-01" || got[1].Volume != 1000000 {
		t.Errorf("second candle mismatch: %+v", got[1])
	}
}

func TestGetCandles_CacheHit_IntervalIsolation(t *testing.T) {
	svc, repo, mr := newTestService(t)
	defer mr.Close()

	dailyCandles := []domain.Candle{{Timestamp: "2024-01-01", Volume: 1000000}}
	weeklyCandles := []domain.Candle{{Timestamp: "2024-01-01", Volume: 5000000}}
	seedCandleCache(t, repo, "005930", domain.IntervalDay, dailyCandles)
	seedCandleCache(t, repo, "005930", domain.Interval("week"), weeklyCandles)

	gotD, err := svc.GetCandles(context.Background(), "005930", domain.IntervalDay, 50, "")
	if err != nil {
		t.Fatalf("unexpected error for day: %v", err)
	}
	gotW, err := svc.GetCandles(context.Background(), "005930", domain.Interval("week"), 50, "")
	if err != nil {
		t.Fatalf("unexpected error for week: %v", err)
	}

	if gotD[0].Volume != 1000000 {
		t.Errorf("daily volume: want 1000000, got %d", gotD[0].Volume)
	}
	if gotW[0].Volume != 5000000 {
		t.Errorf("weekly volume: want 5000000, got %d", gotW[0].Volume)
	}
}

func TestGetCandles_CacheHit_AllFields(t *testing.T) {
	svc, repo, mr := newTestService(t)
	defer mr.Close()

	want := []domain.Candle{
		{Timestamp: "2024-03-15", Open: 72000, High: 73500, Low: 71000, Close: 73000, Volume: 2500000},
	}
	seedCandleCache(t, repo, "000660", domain.IntervalDay, want)

	got, err := svc.GetCandles(context.Background(), "000660", domain.IntervalDay, 1, "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 1 {
		t.Fatalf("expected 1 candle, got %d", len(got))
	}
	c := got[0]
	if c.Open != 72000 || c.High != 73500 || c.Low != 71000 || c.Close != 73000 || c.Volume != 2500000 {
		t.Errorf("candle fields mismatch: %+v", c)
	}
}

// ─── GetTopStocks 테스트 ─────────────────────────────────────────────────────

func TestGetTopStocks_VolumeSorting(t *testing.T) {
	svc, repo, mr := newTestService(t)
	defer mr.Close()

	ctx := context.Background()
	stocks := []*domain.Stock{
		{Ticker: "005930", Name: "삼성전자", CurrentPrice: 70000, ChangeRate: 1.5, AccVolume: 3000000},
		{Ticker: "000660", Name: "SK하이닉스", CurrentPrice: 180000, ChangeRate: -0.5, AccVolume: 5000000},
		{Ticker: "035420", Name: "NAVER", CurrentPrice: 200000, ChangeRate: 0.8, AccVolume: 1000000},
	}
	if err := repo.BulkUpsertStocks(ctx, stocks); err != nil {
		t.Fatalf("setup failed: %v", err)
	}

	result, err := svc.GetTopStocks(ctx, 3, domain.RankTypeVolume)
	if err != nil {
		t.Fatalf("GetTopStocks failed: %v", err)
	}
	if len(result) != 3 {
		t.Fatalf("expected 3 stocks, got %d", len(result))
	}
	// AccVolume 내림차순: SK하이닉스(5M) > 삼성전자(3M) > NAVER(1M)
	if result[0].Ticker != "000660" {
		t.Errorf("rank 1: want 000660, got %s", result[0].Ticker)
	}
	if result[1].Ticker != "005930" {
		t.Errorf("rank 2: want 005930, got %s", result[1].Ticker)
	}
	if result[2].Ticker != "035420" {
		t.Errorf("rank 3: want 035420, got %s", result[2].Ticker)
	}
}

func TestGetTopStocks_LimitRespected(t *testing.T) {
	svc, repo, mr := newTestService(t)
	defer mr.Close()

	ctx := context.Background()
	stocks := []*domain.Stock{
		{Ticker: "005930", AccVolume: 3000000},
		{Ticker: "000660", AccVolume: 5000000},
		{Ticker: "035420", AccVolume: 1000000},
	}
	if err := repo.BulkUpsertStocks(ctx, stocks); err != nil {
		t.Fatalf("setup failed: %v", err)
	}

	result, err := svc.GetTopStocks(ctx, 2, domain.RankTypeVolume)
	if err != nil {
		t.Fatalf("GetTopStocks failed: %v", err)
	}
	if len(result) != 2 {
		t.Errorf("expected 2 stocks, got %d", len(result))
	}
}

// ─── GetOrderbook 테스트 ─────────────────────────────────────────────────────

func TestGetOrderbook_Success(t *testing.T) {
	svc, _, mr := newTestService(t)
	defer mr.Close()

	obData := `{"ticker":"005930","name":"삼성전자","askPrice1":80600,"askVolume1":15400,"bidPrice1":80500,"bidVolume1":32000}`
	mr.Set("stocks:orderbook:005930", obData)
	mr.HSet("stocks:current:005930", "price", "80550")
	mr.HSet("stocks:current:005930", "change_rate", "1.25")

	ob, err := svc.GetOrderbook(context.Background(), "005930")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ob == nil {
		t.Fatal("expected non-nil orderbook")
	}
	if ob.Ticker != "005930" || ob.CurrentPrice != 80550 || ob.ChangeRate != 1.25 {
		t.Errorf("orderbook mismatch: %+v", ob)
	}
}

func TestGetOrderbook_NotFound(t *testing.T) {
	svc, _, mr := newTestService(t)
	defer mr.Close()

	ob, err := svc.GetOrderbook(context.Background(), "000000")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if ob != nil {
		t.Errorf("expected nil for missing ticker, got %+v", ob)
	}
}

// ─── GetTopStocks 테스트 (continued) ────────────────────────────────────────

func TestGetTopStocks_EmptyRedis(t *testing.T) {
	svc, _, mr := newTestService(t)
	defer mr.Close()

	result, err := svc.GetTopStocks(context.Background(), 40, domain.RankTypeVolume)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(result) != 0 {
		t.Errorf("expected empty slice, got %d", len(result))
	}
}

// ─── endTime 커서 페이징 테스트 ───────────────────────────────────────────────

// TestGetCandles_WithEndTime_SkipsCache
// endTime이 지정되면 Redis 캐시를 무시하고 DB로 직접 요청한다.
// DB가 nil인 테스트 환경에서는 패닉(nil pointer dereference)이 발생해야 한다.
func TestGetCandles_WithEndTime_SkipsCache(t *testing.T) {
	svc, repo, mr := newTestService(t)
	defer mr.Close()

	// 캐시에 데이터가 있어도 endTime이 지정되면 캐시를 건너뛰어야 한다.
	candles := []domain.Candle{
		{Timestamp: "2024-01-01", Close: 70500, Volume: 1000000},
	}
	seedCandleCache(t, repo, "005930", domain.IntervalDay, candles)

	// endTime != "" → GetCandlesFromDB(db=nil) 직접 호출 → nil pointer dereference → panic
	defer func() {
		if r := recover(); r == nil {
			t.Error("expected panic from nil DB when endTime is set, but did not panic")
		}
	}()

	_, _ = svc.GetCandles(context.Background(), "005930", domain.IntervalDay, 10, "2024-01-02")
}
