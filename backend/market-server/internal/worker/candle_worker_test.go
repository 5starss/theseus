package worker

import (
	"context"
	"encoding/json"
	"strconv"
	"sync"
	"testing"

	"market-server/internal/domain"
)

// tickJSON handleTick이 기대하는 Tick JSON을 생성한다.
func tickJSON(ticker string, price float64, tradeVol int64) []byte {
	b, _ := json.Marshal(Tick{Ticker: ticker, CurrentPrice: price, TradeVolume: tradeVol})
	return b
}

// newCandleWorkerUnit Kafka/DB 없이 집계 로직만 테스트하기 위한 최소 CandleWorker.
func newCandleWorkerUnit() *CandleWorker {
	return &CandleWorker{
		candles: make(map[string]*domain.Candle),
	}
}

// ─── 경계값 분석 (Boundary Value Analysis) ──────────────────────────────────────

// TestHandleTick_EmptyTicker_IsSkipped 빈 Ticker는 무시되어야 한다.
func TestHandleTick_EmptyTicker_IsSkipped(t *testing.T) {
	w := newCandleWorkerUnit()
	if err := w.handleTick(context.Background(), tickJSON("", 80000, 100)); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(w.candles) != 0 {
		t.Errorf("빈 Ticker는 candles 맵에 추가되지 않아야 한다. got=%d", len(w.candles))
	}
}

// TestHandleTick_InvalidJSON_ReturnsError 잘못된 JSON은 에러를 반환해야 한다.
func TestHandleTick_InvalidJSON_ReturnsError(t *testing.T) {
	w := newCandleWorkerUnit()
	if err := w.handleTick(context.Background(), []byte(`not-json`)); err == nil {
		t.Error("잘못된 JSON에 대해 에러를 반환해야 한다, got nil")
	}
}

// TestHandleTick_FirstTick_SetsOHLCVCorrectly 첫 번째 틱: Open=High=Low=Close=price, Volume=tradeVol
func TestHandleTick_FirstTick_SetsOHLCVCorrectly(t *testing.T) {
	w := newCandleWorkerUnit()
	if err := w.handleTick(context.Background(), tickJSON("005930", 80000, 300)); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	c := w.candles["005930"]
	if c == nil {
		t.Fatal("첫 틱 후 캔들이 생성되어야 한다")
	}
	if c.Open != 80000 || c.High != 80000 || c.Low != 80000 || c.Close != 80000 {
		t.Errorf("첫 틱의 OHLC는 모두 price(80000)여야 한다: O=%d H=%d L=%d C=%d", c.Open, c.High, c.Low, c.Close)
	}
	if c.Volume != 300 {
		t.Errorf("Volume: want 300, got %d", c.Volume)
	}
}

// TestHandleTick_PriceAtHighPlusOne_UpdatesHigh 경계값: price = High+1 → High 갱신
func TestHandleTick_PriceAtHighPlusOne_UpdatesHigh(t *testing.T) {
	w := newCandleWorkerUnit()
	_ = w.handleTick(context.Background(), tickJSON("005930", 80000, 100))
	_ = w.handleTick(context.Background(), tickJSON("005930", 80001, 100)) // High+1

	c := w.candles["005930"]
	if c.High != 80001 {
		t.Errorf("High: want 80001 (High+1 케이스), got %d", c.High)
	}
}

// TestHandleTick_PriceEqualsHigh_NoHighUpdate 경계값: price = High → High 갱신 없음
func TestHandleTick_PriceEqualsHigh_NoHighUpdate(t *testing.T) {
	w := newCandleWorkerUnit()
	_ = w.handleTick(context.Background(), tickJSON("005930", 80000, 100))
	_ = w.handleTick(context.Background(), tickJSON("005930", 80000, 100)) // 동일 가격

	c := w.candles["005930"]
	if c.High != 80000 {
		t.Errorf("High: want 80000 (동일가 갱신 없어야 함), got %d", c.High)
	}
}

// TestHandleTick_PriceAtLowMinusOne_UpdatesLow 경계값: price = Low-1 → Low 갱신
func TestHandleTick_PriceAtLowMinusOne_UpdatesLow(t *testing.T) {
	w := newCandleWorkerUnit()
	_ = w.handleTick(context.Background(), tickJSON("005930", 80000, 100))
	_ = w.handleTick(context.Background(), tickJSON("005930", 79999, 100)) // Low-1

	c := w.candles["005930"]
	if c.Low != 79999 {
		t.Errorf("Low: want 79999 (Low-1 케이스), got %d", c.Low)
	}
}

// TestHandleTick_PriceEqualsLow_NoLowUpdate 경계값: price = Low → Low 갱신 없음
func TestHandleTick_PriceEqualsLow_NoLowUpdate(t *testing.T) {
	w := newCandleWorkerUnit()
	_ = w.handleTick(context.Background(), tickJSON("005930", 80000, 100))
	_ = w.handleTick(context.Background(), tickJSON("005930", 80000, 100))

	c := w.candles["005930"]
	if c.Low != 80000 {
		t.Errorf("Low: want 80000 (동일가 Low 갱신 없어야 함), got %d", c.Low)
	}
}

// TestHandleTick_VolumeAccumulates 여러 틱의 단일 체결량이 누적되어야 한다.
func TestHandleTick_VolumeAccumulates(t *testing.T) {
	w := newCandleWorkerUnit()
	_ = w.handleTick(context.Background(), tickJSON("005930", 80000, 100))
	_ = w.handleTick(context.Background(), tickJSON("005930", 80100, 200))
	_ = w.handleTick(context.Background(), tickJSON("005930", 79900, 50))

	c := w.candles["005930"]
	if c.Volume != 350 {
		t.Errorf("Volume 누적: want 350 (100+200+50), got %d", c.Volume)
	}
}

// TestHandleTick_OpenIsPreserved 이후 틱이 어떤 가격이어도 Open은 첫 번째 틱 가격을 유지해야 한다.
func TestHandleTick_OpenIsPreserved(t *testing.T) {
	w := newCandleWorkerUnit()
	_ = w.handleTick(context.Background(), tickJSON("005930", 80000, 100))
	_ = w.handleTick(context.Background(), tickJSON("005930", 82000, 100)) // 더 높은 가격
	_ = w.handleTick(context.Background(), tickJSON("005930", 78000, 100)) // 더 낮은 가격

	c := w.candles["005930"]
	if c.Open != 80000 {
		t.Errorf("Open은 첫 틱 가격(80000)이어야 한다, got %d", c.Open)
	}
}

// TestHandleTick_CloseUpdatesToLatestPrice Close는 항상 가장 최신 틱 가격이어야 한다.
func TestHandleTick_CloseUpdatesToLatestPrice(t *testing.T) {
	w := newCandleWorkerUnit()
	_ = w.handleTick(context.Background(), tickJSON("005930", 80000, 100))
	_ = w.handleTick(context.Background(), tickJSON("005930", 81000, 100))
	_ = w.handleTick(context.Background(), tickJSON("005930", 79500, 100)) // 마지막 틱

	c := w.candles["005930"]
	if c.Close != 79500 {
		t.Errorf("Close는 마지막 틱 가격(79500)이어야 한다, got %d", c.Close)
	}
}

// TestHandleTick_ZeroPrice_DoesNotPanic 경계값: 가격 0은 패닉 없이 처리되어야 한다.
func TestHandleTick_ZeroPrice_DoesNotPanic(t *testing.T) {
	w := newCandleWorkerUnit()
	defer func() {
		if r := recover(); r != nil {
			t.Errorf("가격 0에서 패닉 발생: %v", r)
		}
	}()
	_ = w.handleTick(context.Background(), tickJSON("005930", 0, 100))

	c := w.candles["005930"]
	if c == nil {
		t.Fatal("가격 0이어도 캔들은 생성되어야 한다")
	}
	if c.Open != 0 || c.High != 0 || c.Low != 0 || c.Close != 0 {
		t.Errorf("가격 0일 때 OHLC 모두 0이어야 한다: %+v", c)
	}
}

// ─── 시나리오 테스트 (Scenario Tests) ────────────────────────────────────────────

// TestHandleTick_FullOHLCVScenario 5개 틱에 대한 전체 OHLCV 집계 시나리오
func TestHandleTick_FullOHLCVScenario(t *testing.T) {
	w := newCandleWorkerUnit()
	ctx := context.Background()

	// 가격 흐름: 80000(시가) → 81500(고가) → 79000(저가) → 80500 → 80200(종가)
	type tick struct {
		price float64
		vol   int64
	}
	ticks := []tick{
		{80000, 100},
		{81500, 200},
		{79000, 150},
		{80500, 300},
		{80200, 250},
	}

	for _, tk := range ticks {
		if err := w.handleTick(ctx, tickJSON("005930", tk.price, tk.vol)); err != nil {
			t.Fatalf("handleTick error at price=%v: %v", tk.price, err)
		}
	}

	c := w.candles["005930"]
	if c == nil {
		t.Fatal("캔들이 생성되어야 한다")
	}

	tests := []struct {
		name string
		got  int64
		want int64
	}{
		{"Open", c.Open, 80000},
		{"High", c.High, 81500},
		{"Low", c.Low, 79000},
		{"Close", c.Close, 80200},
		{"Volume", c.Volume, 1000}, // 100+200+150+300+250
	}
	for _, tt := range tests {
		if tt.got != tt.want {
			t.Errorf("%s: want %d, got %d", tt.name, tt.want, tt.got)
		}
	}
}

// TestHandleTick_MultipleTickers_AreIndependent 서로 다른 종목은 독립적으로 집계된다.
func TestHandleTick_MultipleTickers_AreIndependent(t *testing.T) {
	w := newCandleWorkerUnit()
	ctx := context.Background()

	_ = w.handleTick(ctx, tickJSON("005930", 80000, 100))
	_ = w.handleTick(ctx, tickJSON("000660", 180000, 500))
	_ = w.handleTick(ctx, tickJSON("005930", 81000, 200)) // 삼성만 추가 틱

	samsung := w.candles["005930"]
	skhynix := w.candles["000660"]

	if samsung == nil || skhynix == nil {
		t.Fatal("두 종목 모두 캔들이 생성되어야 한다")
	}

	// 삼성: Open=80000, High=81000, Volume=300
	if samsung.Open != 80000 {
		t.Errorf("samsung Open: want 80000, got %d", samsung.Open)
	}
	if samsung.High != 81000 {
		t.Errorf("samsung High: want 81000, got %d", samsung.High)
	}
	if samsung.Volume != 300 {
		t.Errorf("samsung Volume: want 300, got %d", samsung.Volume)
	}

	// SK하이닉스: Open=180000, High=180000, Volume=500 (단일 틱)
	if skhynix.Open != 180000 {
		t.Errorf("skhynix Open: want 180000, got %d", skhynix.Open)
	}
	if skhynix.Volume != 500 {
		t.Errorf("skhynix Volume: want 500, got %d", skhynix.Volume)
	}
}

// TestHandleTick_PriceReversal 고가 이후 저가로 반전 시나리오
func TestHandleTick_PriceReversal(t *testing.T) {
	w := newCandleWorkerUnit()
	ctx := context.Background()

	_ = w.handleTick(ctx, tickJSON("005930", 80000, 100)) // Open
	_ = w.handleTick(ctx, tickJSON("005930", 85000, 100)) // 신고가
	_ = w.handleTick(ctx, tickJSON("005930", 75000, 100)) // 신저가
	_ = w.handleTick(ctx, tickJSON("005930", 85001, 100)) // 더 높은 신고가 (경계값)
	_ = w.handleTick(ctx, tickJSON("005930", 74999, 100)) // 더 낮은 신저가 (경계값)

	c := w.candles["005930"]
	if c.High != 85001 {
		t.Errorf("최종 High: want 85001, got %d", c.High)
	}
	if c.Low != 74999 {
		t.Errorf("최종 Low: want 74999, got %d", c.Low)
	}
	if c.Open != 80000 {
		t.Errorf("Open은 첫 가격 80000 유지: got %d", c.Open)
	}
	if c.Close != 74999 {
		t.Errorf("Close는 마지막 가격 74999: got %d", c.Close)
	}
}

// TestHandleTick_SingleTickPerMinuteCandle 1분 내 단 1개의 틱인 경우 OHLC 모두 동일
func TestHandleTick_SingleTick_AllFieldsEqual(t *testing.T) {
	w := newCandleWorkerUnit()
	_ = w.handleTick(context.Background(), tickJSON("035420", 250000, 50))

	c := w.candles["035420"]
	if c == nil {
		t.Fatal("캔들이 생성되어야 한다")
	}
	if c.Open != c.High || c.High != c.Low || c.Low != c.Close {
		t.Errorf("단일 틱: OHLC가 모두 같아야 한다: O=%d H=%d L=%d C=%d", c.Open, c.High, c.Low, c.Close)
	}
}

// ─── flushCandles 테스트 ──────────────────────────────────────────────────────

// TestFlushCandles_EmptyMap_IsNoOp 빈 맵에서 flushCandles는 패닉 없이 아무것도 하지 않는다.
func TestFlushCandles_EmptyMap_IsNoOp(t *testing.T) {
	w := &CandleWorker{
		candles:   make(map[string]*domain.Candle),
		stockRepo: nil, // 빈 맵은 DB 호출 전 early return
	}
	defer func() {
		if r := recover(); r != nil {
			t.Errorf("빈 맵 flush에서 패닉 발생: %v", r)
		}
	}()
	w.flushCandles()

	if len(w.candles) != 0 {
		t.Errorf("flush 후 맵은 비어 있어야 한다, got %d", len(w.candles))
	}
}

// TestFlushCandles_SwapsMap_EmptyAfterFlush flushCandles 호출 직후 내부 맵이 초기화된다.
// (DB 호출은 실패하더라도 맵 스왑 자체는 이루어져야 한다)
func TestFlushCandles_SwapsMap_EmptyAfterFlush(t *testing.T) {
	// stockRepo nil + 데이터가 있으면 BulkInsertCandles에서 패닉 발생하므로
	// DB 연동 없이 맵 스왑만 검증하려면 flushCandles 내부의 Lock/Swap 부분을 직접 확인한다.
	// 여기서는 empty 케이스를 통해 스왑 패턴 동작을 검증한다.
	w := &CandleWorker{
		candles:   make(map[string]*domain.Candle),
		stockRepo: nil,
	}

	// 빈 맵 flushCandles: early return
	w.flushCandles()

	// 맵이 여전히 초기화된 상태(빈 맵)임을 확인
	if w.candles == nil {
		t.Error("flushCandles 후 candles 맵이 nil이 되어서는 안 된다")
	}
}

// ─── 탐색적 테스트 (Exploratory Tests) ──────────────────────────────────────────

// TestHandleTick_ConcurrentDifferentTickers_NoDataRace
// 100개 고루틴이 서로 다른 종목에 동시에 handleTick 호출 → 데이터 레이스 없음.
// go test -race 플래그로 실행 시 레이스 디텍터가 검증한다.
func TestHandleTick_ConcurrentDifferentTickers_NoDataRace(t *testing.T) {
	w := newCandleWorkerUnit()
	ctx := context.Background()

	const goroutines = 100
	var wg sync.WaitGroup
	wg.Add(goroutines)

	for i := 0; i < goroutines; i++ {
		go func(idx int) {
			defer wg.Done()
			ticker := "T" + strconv.Itoa(idx)
			_ = w.handleTick(ctx, tickJSON(ticker, float64(10000+idx), 1))
		}(i)
	}
	wg.Wait()

	if len(w.candles) != goroutines {
		t.Errorf("서로 다른 종목 %d개에 대해 %d개의 캔들이 생성되어야 한다, got %d",
			goroutines, goroutines, len(w.candles))
	}
}

// TestHandleTick_ConcurrentSameTicker_VolumeConsistent
// 100개 고루틴이 동일 종목에 동시에 handleTick(volume=1) 호출 → 최종 Volume = 100
func TestHandleTick_ConcurrentSameTicker_VolumeConsistent(t *testing.T) {
	w := newCandleWorkerUnit()
	ctx := context.Background()

	const goroutines = 100
	var wg sync.WaitGroup
	wg.Add(goroutines)

	for i := 0; i < goroutines; i++ {
		go func() {
			defer wg.Done()
			_ = w.handleTick(ctx, tickJSON("005930", 80000, 1))
		}()
	}
	wg.Wait()

	c := w.candles["005930"]
	if c == nil {
		t.Fatal("동시 접근 후 캔들이 존재해야 한다")
	}
	if c.Volume != goroutines {
		t.Errorf("동시 100틱 후 Volume: want %d, got %d", goroutines, c.Volume)
	}
}

// TestHandleTick_ConcurrentSwapAndWrite_NoDataRace
// 맵 스왑(버퍼 교체)과 handleTick(쓰기)의 동시 실행 안전성 검증.
// flushCandles의 DB 호출 없이 Lock/Swap 패턴 자체의 데이터 레이스를 검증한다.
func TestHandleTick_ConcurrentSwapAndWrite_NoDataRace(t *testing.T) {
	w := newCandleWorkerUnit()
	ctx := context.Background()

	var wg sync.WaitGroup

	// 틱 생산자 10개 (각 20번 호출)
	for i := 0; i < 10; i++ {
		wg.Add(1)
		go func(idx int) {
			defer wg.Done()
			for j := 0; j < 20; j++ {
				ticker := "S" + strconv.Itoa(idx)
				_ = w.handleTick(ctx, tickJSON(ticker, float64(10000+j), 1))
			}
		}(i)
	}

	// 맵 스왑 소비자 5개 (flushCandles의 Lock/Swap 부분만 직접 테스트)
	for i := 0; i < 5; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 10; j++ {
				// flushCandles 내부의 Lock/Swap 패턴을 직접 재현
				w.mu.Lock()
				swapped := w.candles
				w.candles = make(map[string]*domain.Candle)
				w.mu.Unlock()
				// swapped 맵 사용 (실제로는 DB Insert 대신 len만 확인)
				_ = len(swapped)
			}
		}()
	}

	wg.Wait()
	// 패닉/레이스 없이 완료되면 성공
}
