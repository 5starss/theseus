package service

import (
	"context"
	"fmt"
	"testing"
	"time"

	"market-server/internal/domain"
	"market-server/internal/repository"

	"github.com/alicebob/miniredis/v2"
	"github.com/redis/go-redis/v9"
)

// ─── 1d 인터벌 On-the-fly 캔들 테스트 헬퍼 ──────────────────────────────────

func newTestService1d(t *testing.T) (*StockService, *repository.StockRepository, *miniredis.Miniredis) {
	t.Helper()
	mr, err := miniredis.Run()
	if err != nil {
		t.Fatalf("miniredis start failed: %v", err)
	}
	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	repo := repository.NewStockRepository(rdb, nil)
	return NewStockService(repo), repo, mr
}

// seedPastDailyCandles 1d 캔들 ZSet 캐시에 과거 날짜 데이터를 세팅한다.
// Timestamp 포맷은 반드시 "2006-01-02" (MySQL DATE 형식) 이어야 한다.
func seedPastDailyCandles(t *testing.T, repo *repository.StockRepository, ticker string, candles []domain.Candle) {
	t.Helper()
	if err := repo.SaveCandlesToCache(context.Background(), ticker, domain.IntervalDay, candles); err != nil {
		t.Fatalf("seedPastDailyCandles failed: %v", err)
	}
}

// seedLiveCurrentData stocks:current:{ticker} 해시에 실시간 체결 데이터를 세팅한다.
func seedLiveCurrentData(t *testing.T, mr *miniredis.Miniredis, ticker string, price, open, high, low float64, accVol int64) {
	t.Helper()
	key := "stocks:current:" + ticker
	mr.HSet(key, "price", fmt.Sprintf("%v", price))
	mr.HSet(key, "open", fmt.Sprintf("%v", open))
	mr.HSet(key, "high", fmt.Sprintf("%v", high))
	mr.HSet(key, "low", fmt.Sprintf("%v", low))
	mr.HSet(key, "acc_vol", fmt.Sprintf("%d", accVol))
}

// yesterdayStr 어제 날짜 문자열 (서비스와 동일한 2006-01-02 포맷)
func yesterdayStr() string {
	return time.Now().AddDate(0, 0, -1).Format("2006-01-02")
}

// todayStr 오늘 날짜 문자열 (서비스와 동일한 2006-01-02 포맷)
func todayStr() string {
	return time.Now().Format("2006-01-02")
}

// ─── 시나리오: 1d 당일 캔들 On-the-fly 추가 ─────────────────────────────────

// TestGetCandles_1d_PrependsTodayLiveCandle
// 과거 일봉 캐시 + 실시간 Redis 데이터 → 결과 첫 번째가 오늘 캔들이어야 한다.
func TestGetCandles_1d_PrependsTodayLiveCandle(t *testing.T) {
	svc, repo, mr := newTestService1d(t)
	defer mr.Close()

	past := []domain.Candle{
		{Timestamp: yesterdayStr(), Open: 79000, High: 80000, Low: 78000, Close: 79500, Volume: 1000000},
		{Timestamp: time.Now().AddDate(0, 0, -2).Format("2006-01-02"), Open: 78000, High: 79000, Low: 77000, Close: 78500, Volume: 900000},
	}
	seedPastDailyCandles(t, repo, "005930", past)
	seedLiveCurrentData(t, mr, "005930", 80500, 79000, 81000, 78500, 2000000)

	got, err := svc.GetCandles(context.Background(), "005930", domain.IntervalDay, 50, "")
	if err != nil {
		t.Fatalf("GetCandles error: %v", err)
	}

	// 오늘 캔들이 맨 앞에 추가되어 총 3개여야 한다.
	if len(got) != 3 {
		t.Fatalf("want 3 candles (1 today + 2 past), got %d", len(got))
	}

	today := got[0]
	if today.Timestamp != todayStr() {
		t.Errorf("첫 번째 캔들 날짜: want %s (오늘), got %s", todayStr(), today.Timestamp)
	}
	if today.Close != 80500 {
		t.Errorf("Close: want 80500 (현재가), got %d", today.Close)
	}
	if today.Open != 79000 {
		t.Errorf("Open: want 79000 (시가), got %d", today.Open)
	}
	if today.High != 81000 {
		t.Errorf("High: want 81000 (고가), got %d", today.High)
	}
	if today.Low != 78500 {
		t.Errorf("Low: want 78500 (저가), got %d", today.Low)
	}
	if today.Volume != 2000000 {
		t.Errorf("Volume: want 2000000 (누적거래량), got %d", today.Volume)
	}

	// 과거 캔들이 뒤에 유지되어야 한다.
	if got[1].Timestamp != yesterdayStr() {
		t.Errorf("두 번째 캔들: want %s (어제), got %s", yesterdayStr(), got[1].Timestamp)
	}
}

// TestGetCandles_1d_ReplacesTodaysExistingCandle
// 캐시의 첫 번째 캔들이 오늘 날짜인 경우 → 실시간 데이터로 덮어써야 한다.
func TestGetCandles_1d_ReplacesTodaysExistingCandle(t *testing.T) {
	svc, repo, mr := newTestService1d(t)
	defer mr.Close()

	// 캐시에 오늘 날짜 캔들이 이미 있는 상태 (과거 가격)
	cachedToday := domain.Candle{
		Timestamp: todayStr(),
		Open:      79000, High: 80000, Low: 78000, Close: 79000, Volume: 500000,
	}
	past := []domain.Candle{
		cachedToday,
		{Timestamp: yesterdayStr(), Open: 78000, High: 79000, Low: 77000, Close: 78500, Volume: 900000},
	}
	seedPastDailyCandles(t, repo, "005930", past)

	// 실시간 최신 가격 (캐시보다 높은 가격)
	seedLiveCurrentData(t, mr, "005930", 80500, 79000, 81000, 78500, 2000000)

	got, err := svc.GetCandles(context.Background(), "005930", domain.IntervalDay, 50, "")
	if err != nil {
		t.Fatalf("GetCandles error: %v", err)
	}

	// 캔들 개수는 그대로 2개 (오늘 캔들 교체, 추가 아님)
	if len(got) != 2 {
		t.Fatalf("오늘 캔들 교체 시 총 개수 유지: want 2, got %d", len(got))
	}

	today := got[0]
	if today.Timestamp != todayStr() {
		t.Errorf("첫 번째 캔들 날짜: want %s, got %s", todayStr(), today.Timestamp)
	}
	// 실시간 데이터로 덮어써야 한다 (Close: 79000 → 80500)
	if today.Close != 80500 {
		t.Errorf("Close: want 80500 (실시간 덮어쓰기), got %d", today.Close)
	}
}

// TestGetCandles_1d_LimitTruncatesAfterPrepend
// 오늘 캔들 추가 후 limit을 초과하면 잘라내야 한다.
func TestGetCandles_1d_LimitTruncatesAfterPrepend(t *testing.T) {
	svc, repo, mr := newTestService1d(t)
	defer mr.Close()

	// 과거 캔들 5개 (오늘 날짜 없음), "2006-01-02" 포맷 사용
	past := make([]domain.Candle, 5)
	for i := range past {
		past[i] = domain.Candle{
			Timestamp: time.Now().AddDate(0, 0, -(i + 1)).Format("2006-01-02"),
			Open:      int64(79000 - i*100), High: int64(80000 - i*100),
			Low:       int64(78000 - i*100), Close: int64(79500 - i*100),
			Volume:    int64(1000000 - i*10000),
		}
	}
	seedPastDailyCandles(t, repo, "005930", past)
	seedLiveCurrentData(t, mr, "005930", 80500, 79000, 81000, 78500, 2000000)

	// limit=5 → 오늘 추가(6개) 후 5개로 잘라야 함
	got, err := svc.GetCandles(context.Background(), "005930", domain.IntervalDay, 5, "")
	if err != nil {
		t.Fatalf("GetCandles error: %v", err)
	}
	if len(got) != 5 {
		t.Errorf("limit=5 적용: want 5, got %d", len(got))
	}
	if got[0].Timestamp != todayStr() {
		t.Errorf("첫 번째는 오늘 캔들이어야 한다, got %s", got[0].Timestamp)
	}
}

// TestGetCandles_1d_NoTickSnapshot_ReturnsHistoricalOnly
// stocks:current에 데이터가 없는 경우 → 과거 캔들만 반환, 오늘 캔들 추가 안 함.
func TestGetCandles_1d_NoTickSnapshot_ReturnsHistoricalOnly(t *testing.T) {
	svc, repo, mr := newTestService1d(t)
	defer mr.Close()

	past := []domain.Candle{
		{Timestamp: yesterdayStr(), Open: 79000, High: 80000, Low: 78000, Close: 79500, Volume: 1000000},
	}
	seedPastDailyCandles(t, repo, "005930", past)
	// stocks:current 설정 없음 → GetTickSnapshot returns nil
	_ = mr

	got, err := svc.GetCandles(context.Background(), "005930", domain.IntervalDay, 50, "")
	if err != nil {
		t.Fatalf("GetCandles error: %v", err)
	}
	if len(got) != 1 {
		t.Fatalf("실시간 없으면 과거 1개만 반환: want 1, got %d", len(got))
	}
	if got[0].Timestamp != yesterdayStr() {
		t.Errorf("과거 캔들 날짜: want %s, got %s", yesterdayStr(), got[0].Timestamp)
	}
}

// TestGetCandles_1d_ZeroCurrentPrice_NoPrepend
// 실시간 가격이 0이면 오늘 캔들을 추가하지 않아야 한다.
func TestGetCandles_1d_ZeroCurrentPrice_NoPrepend(t *testing.T) {
	svc, repo, mr := newTestService1d(t)
	defer mr.Close()

	past := []domain.Candle{
		{Timestamp: yesterdayStr(), Open: 79000, High: 80000, Low: 78000, Close: 79500, Volume: 1000000},
	}
	seedPastDailyCandles(t, repo, "005930", past)

	// 가격 0으로 세팅 (장 전, 또는 데이터 오류 상황)
	seedLiveCurrentData(t, mr, "005930", 0, 0, 0, 0, 0)

	got, err := svc.GetCandles(context.Background(), "005930", domain.IntervalDay, 50, "")
	if err != nil {
		t.Fatalf("GetCandles error: %v", err)
	}
	if len(got) != 1 {
		t.Fatalf("현재가=0이면 오늘 캔들 추가 안 함: want 1, got %d", len(got))
	}
	if got[0].Timestamp == todayStr() {
		t.Errorf("현재가=0이면 오늘 캔들이 추가되어선 안 된다")
	}
}

// TestGetCandles_1d_LiveCandleOHLCFromCurrentHash
// 당일 캔들의 Open/High/Low/Close/Volume이 stocks:current에서 올바르게 매핑된다.
func TestGetCandles_1d_LiveCandleOHLCFromCurrentHash(t *testing.T) {
	svc, repo, mr := newTestService1d(t)
	defer mr.Close()

	seedPastDailyCandles(t, repo, "000660", []domain.Candle{
		{Timestamp: yesterdayStr(), Open: 180000, High: 182000, Low: 178000, Close: 181000, Volume: 3000000},
	})
	// SK하이닉스 당일 데이터
	seedLiveCurrentData(t, mr, "000660", 183000, 181000, 185000, 179000, 4500000)

	got, err := svc.GetCandles(context.Background(), "000660", domain.IntervalDay, 50, "")
	if err != nil {
		t.Fatalf("GetCandles error: %v", err)
	}
	if len(got) < 1 {
		t.Fatal("결과가 비어 있음")
	}

	today := got[0]
	checks := []struct {
		field string
		want  int64
		got   int64
	}{
		{"Open", 181000, today.Open},
		{"High", 185000, today.High},
		{"Low", 179000, today.Low},
		{"Close", 183000, today.Close},    // CurrentPrice
		{"Volume", 4500000, today.Volume}, // AccVolume
	}
	for _, c := range checks {
		if c.got != c.want {
			t.Errorf("당일 캔들 %s: want %d, got %d", c.field, c.want, c.got)
		}
	}
}

// TestGetCandles_1d_CacheHit_NoLiveData_ReturnsCache
// 캐시에 데이터가 있고 실시간이 없는 경우 → 캐시 데이터 그대로 반환 (DB 호출 없음).
func TestGetCandles_1d_CacheHit_NoLiveData_ReturnsCache(t *testing.T) {
	svc, repo, mr := newTestService1d(t)
	defer mr.Close()

	past := []domain.Candle{
		{Timestamp: yesterdayStr(), Open: 79000, High: 80000, Low: 78000, Close: 79500, Volume: 1000000},
		{Timestamp: time.Now().AddDate(0, 0, -2).Format("2006-01-02"), Open: 78000, High: 79000, Low: 77000, Close: 78500, Volume: 900000},
	}
	seedPastDailyCandles(t, repo, "005930", past)
	// 실시간 데이터 없음 → 과거 데이터만 반환
	_ = mr

	got, err := svc.GetCandles(context.Background(), "005930", domain.IntervalDay, 50, "")
	if err != nil {
		t.Fatalf("GetCandles error: %v", err)
	}
	if len(got) != 2 {
		t.Fatalf("실시간 없으면 과거 2개 그대로: want 2, got %d", len(got))
	}
	// 오늘 날짜 캔들이 추가되지 않아야 함
	if got[0].Timestamp == todayStr() {
		t.Errorf("실시간 없는데 오늘 캔들이 추가됨: got[0].Timestamp = %s", got[0].Timestamp)
	}
}

// ─── 경계값: 1d limit 파라미터 ───────────────────────────────────────────────

// TestGetCandles_1d_LimitZero_ReturnsAllCandles
// limit=0은 제한 없이 모두 반환해야 한다 (캐시 히트 경우).
func TestGetCandles_1d_LimitZero_ReturnsAllCandles(t *testing.T) {
	svc, repo, mr := newTestService1d(t)
	defer mr.Close()

	// "2006-01-02" 포맷 사용
	past := make([]domain.Candle, 10)
	for i := range past {
		past[i] = domain.Candle{
			Timestamp: time.Now().AddDate(0, 0, -(i + 1)).Format("2006-01-02"),
			Volume:    int64(i + 1),
		}
	}
	seedPastDailyCandles(t, repo, "005930", past)
	seedLiveCurrentData(t, mr, "005930", 80000, 79000, 81000, 78500, 2000000)

	// limit=0은 캐시에서 반환된 전체 + 오늘 캔들 prepend
	got, err := svc.GetCandles(context.Background(), "005930", domain.IntervalDay, 0, "")
	if err != nil {
		t.Fatalf("GetCandles error: %v", err)
	}
	// 오늘 추가 → 11개 (limit=0이므로 truncation 없음)
	if len(got) != 11 {
		t.Errorf("limit=0: want 11 (10 past + 1 today), got %d", len(got))
	}
}

// TestGetCandles_1d_LimitOne_ReturnsOnlyToday
// limit=1이고 실시간 데이터가 있는 경우 → 오늘 캔들만 반환.
func TestGetCandles_1d_LimitOne_ReturnsOnlyToday(t *testing.T) {
	svc, repo, mr := newTestService1d(t)
	defer mr.Close()

	past := []domain.Candle{
		{Timestamp: yesterdayStr(), Volume: 1000000},
		{Timestamp: time.Now().AddDate(0, 0, -2).Format("2006-01-02"), Volume: 900000},
	}
	seedPastDailyCandles(t, repo, "005930", past)
	seedLiveCurrentData(t, mr, "005930", 80000, 79000, 81000, 78500, 2000000)

	got, err := svc.GetCandles(context.Background(), "005930", domain.IntervalDay, 1, "")
	if err != nil {
		t.Fatalf("GetCandles error: %v", err)
	}
	if len(got) != 1 {
		t.Errorf("limit=1: want 1, got %d", len(got))
	}
	if got[0].Timestamp != todayStr() {
		t.Errorf("limit=1 결과: want today(%s), got %s", todayStr(), got[0].Timestamp)
	}
}
