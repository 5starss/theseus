package handler

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"market-server/internal/domain"
	"market-server/internal/repository"
	"market-server/internal/service"

	"github.com/alicebob/miniredis/v2"
	"github.com/gin-gonic/gin"
	"github.com/redis/go-redis/v9"
)

func init() {
	gin.SetMode(gin.TestMode)
}

type apiResp struct {
	IsSuccess bool            `json:"isSuccess"`
	Code      string          `json:"code"`
	Result    json.RawMessage `json:"result"`
}

// newTestComponents miniredis 기반 핸들러, 리포지토리, miniredis를 반환한다.
func newTestComponents(t *testing.T) (*StockHandler, *repository.StockRepository, *miniredis.Miniredis) {
	t.Helper()
	mr, err := miniredis.Run()
	if err != nil {
		t.Fatalf("miniredis start failed: %v", err)
	}
	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	repo := repository.NewStockRepository(rdb, nil)
	svc := service.NewStockService(repo)
	return NewStockHandler(svc), repo, mr
}

func newRouter(h *StockHandler) *gin.Engine {
	r := gin.New()
	r.GET("/api/v1/stocks", h.GetStockList)
	r.GET("/api/v1/stocks/:ticker/candles", h.GetCandles)
	return r
}

// ─── GetCandles 핸들러 테스트 ─────────────────────────────────────────────────

func TestGetCandles_Success(t *testing.T) {
	h, repo, mr := newTestComponents(t)
	defer mr.Close()

	candles := []domain.Candle{
		{Timestamp: "20240101", Open: 70000, High: 71000, Low: 69000, Close: 70500, Volume: 1000000},
		{Timestamp: "20240102", Open: 70500, High: 72000, Low: 70000, Close: 71500, Volume: 1200000},
	}
	repo.SaveCandlesToCache(context.Background(), "005930", domain.IntervalDay, candles)

	r := newRouter(h)
	w := httptest.NewRecorder()
	req, _ := http.NewRequest(http.MethodGet, "/api/v1/stocks/005930/candles?interval=D&limit=50", nil)
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp apiResp
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if !resp.IsSuccess {
		t.Error("expected isSuccess=true")
	}

	var result []domain.Candle
	if err := json.Unmarshal(resp.Result, &result); err != nil {
		t.Fatalf("failed to parse result: %v", err)
	}
	if len(result) != 2 {
		t.Errorf("expected 2 candles, got %d", len(result))
	}
	if result[0].Timestamp != "20240102" || result[0].Close != 71500 {
		t.Errorf("unexpected first candle: %+v", result[0])
	}
}

func TestGetCandles_DefaultInterval(t *testing.T) {
	h, repo, mr := newTestComponents(t)
	defer mr.Close()

	// interval 미지정 시 "D" -> domain.IntervalDay 로 맵핑되어 캐시에서 조회해야 함
	candles := []domain.Candle{{Timestamp: "20240101", Close: 70500}}
	repo.SaveCandlesToCache(context.Background(), "005930", domain.IntervalDay, candles)

	r := newRouter(h)
	w := httptest.NewRecorder()
	req, _ := http.NewRequest(http.MethodGet, "/api/v1/stocks/005930/candles", nil)
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", w.Code)
	}
}

func TestGetCandles_InvalidLimit_Zero(t *testing.T) {
	h, _, mr := newTestComponents(t)
	defer mr.Close()

	r := newRouter(h)
	w := httptest.NewRecorder()
	req, _ := http.NewRequest(http.MethodGet, "/api/v1/stocks/005930/candles?limit=0", nil)
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", w.Code)
	}

	var resp apiResp
	_ = json.Unmarshal(w.Body.Bytes(), &resp)
	if resp.IsSuccess {
		t.Error("expected isSuccess=false")
	}
}

func TestGetCandles_InvalidLimit_Negative(t *testing.T) {
	h, _, mr := newTestComponents(t)
	defer mr.Close()

	r := newRouter(h)
	w := httptest.NewRecorder()
	req, _ := http.NewRequest(http.MethodGet, "/api/v1/stocks/005930/candles?limit=-5", nil)
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", w.Code)
	}
}

func TestGetCandles_InvalidLimit_NotANumber(t *testing.T) {
	h, _, mr := newTestComponents(t)
	defer mr.Close()

	r := newRouter(h)
	w := httptest.NewRecorder()
	req, _ := http.NewRequest(http.MethodGet, "/api/v1/stocks/005930/candles?limit=abc", nil)
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", w.Code)
	}
}

// TestGetCandles_WithEndTime_Returns500WhenNoDB
// endTime 파라미터가 지정되면 캐시를 우회하여 DB를 직접 조회한다.
// 테스트 환경에서 DB는 nil이므로 패닉이 발생 → gin.Recovery()가 500을 반환한다.
func TestGetCandles_WithEndTime_Returns500WhenNoDB(t *testing.T) {
	h, repo, mr := newTestComponents(t)
	defer mr.Close()

	// 캐시에 데이터가 있어도 endTime이 있으면 DB를 직접 조회해야 한다
	candles := []domain.Candle{
		{Timestamp: "2024-01-01", Close: 70500, Volume: 1000000},
	}
	repo.SaveCandlesToCache(context.Background(), "005930", domain.IntervalDay, candles)

	// gin.Recovery() 미들웨어로 nil DB panic → 500 응답
	r := gin.New()
	r.Use(gin.Recovery())
	r.GET("/api/v1/stocks/:ticker/candles", h.GetCandles)

	w := httptest.NewRecorder()
	req, _ := http.NewRequest(http.MethodGet, "/api/v1/stocks/005930/candles?interval=D&limit=10&endTime=2024-01-02", nil)
	r.ServeHTTP(w, req)

	if w.Code != http.StatusInternalServerError {
		t.Errorf("expected 500 (nil DB panic recovered), got %d: %s", w.Code, w.Body.String())
	}
}

// ─── GetStockList 핸들러 테스트 ───────────────────────────────────────────────

func TestGetStockList_Success(t *testing.T) {
	h, repo, mr := newTestComponents(t)
	defer mr.Close()

	stocks := []*domain.Stock{
		{Ticker: "005930", Name: "삼성전자", CurrentPrice: 70000, ChangeRate: 1.5, AccVolume: 3000000},
		{Ticker: "000660", Name: "SK하이닉스", CurrentPrice: 180000, ChangeRate: -0.5, AccVolume: 5000000},
	}
	if err := repo.BulkUpsertStocks(t.Context(), stocks); err != nil {
		t.Fatalf("setup failed: %v", err)
	}

	r := newRouter(h)
	w := httptest.NewRecorder()
	req, _ := http.NewRequest(http.MethodGet, "/api/v1/stocks?limit=2&rankType=VOLUME", nil)
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp apiResp
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}
	if !resp.IsSuccess {
		t.Error("expected isSuccess=true")
	}

	var result []domain.Stock
	if err := json.Unmarshal(resp.Result, &result); err != nil {
		t.Fatalf("failed to parse result: %v", err)
	}
	if len(result) != 2 {
		t.Errorf("expected 2 stocks, got %d", len(result))
	}
	// AccVolume 내림차순: SK하이닉스 first
	if result[0].Ticker != "000660" {
		t.Errorf("expected 000660 at rank 1, got %s", result[0].Ticker)
	}
}

func TestGetStockList_InvalidLimit_Zero(t *testing.T) {
	h, _, mr := newTestComponents(t)
	defer mr.Close()

	r := newRouter(h)
	w := httptest.NewRecorder()
	req, _ := http.NewRequest(http.MethodGet, "/api/v1/stocks?limit=0", nil)
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", w.Code)
	}
}

func TestGetStockList_InvalidLimit_Over20(t *testing.T) {
	h, _, mr := newTestComponents(t)
	defer mr.Close()

	r := newRouter(h)
	w := httptest.NewRecorder()
	req, _ := http.NewRequest(http.MethodGet, "/api/v1/stocks?limit=21", nil)
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", w.Code)
	}
}

func TestGetStockList_InvalidLimit_NotANumber(t *testing.T) {
	h, _, mr := newTestComponents(t)
	defer mr.Close()

	r := newRouter(h)
	w := httptest.NewRecorder()
	req, _ := http.NewRequest(http.MethodGet, "/api/v1/stocks?limit=xyz", nil)
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", w.Code)
	}
}

func TestGetStockList_InvalidRankType(t *testing.T) {
	h, _, mr := newTestComponents(t)
	defer mr.Close()

	r := newRouter(h)
	w := httptest.NewRecorder()
	req, _ := http.NewRequest(http.MethodGet, "/api/v1/stocks?rankType=INVALID", nil)
	r.ServeHTTP(w, req)

	if w.Code != http.StatusBadRequest {
		t.Errorf("expected 400, got %d", w.Code)
	}
}

func TestGetStockList_EmptyRedis(t *testing.T) {
	h, _, mr := newTestComponents(t)
	defer mr.Close()

	r := newRouter(h)
	w := httptest.NewRecorder()
	req, _ := http.NewRequest(http.MethodGet, "/api/v1/stocks?limit=10", nil)
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("expected 200, got %d", w.Code)
	}

	var resp apiResp
	_ = json.Unmarshal(w.Body.Bytes(), &resp)
	if !resp.IsSuccess {
		t.Error("expected isSuccess=true even when redis is empty")
	}
}

// ─── GetOrderbook 핸들러 테스트 ──────────────────────────────────────────────

func TestGetOrderbook_Success(t *testing.T) {
	h, _, mr := newTestComponents(t)
	defer mr.Close()

	// 1. 호가창 데이터 세팅
	obData := `{"ticker":"005930","name":"삼성전자","askPrice1":80600,"askVolume1":15400,"bidPrice1":80500,"bidVolume1":32000}`
	mr.Set("stocks:orderbook:005930", obData)

	// 2. 체결가(현재가) 데이터 세팅
	mr.HSet("stocks:current:005930", "price", "80550")
	mr.HSet("stocks:current:005930", "change_rate", "1.25")

	r := gin.New()
	r.GET("/api/v1/stocks/:ticker/orderbook", h.GetOrderbook)

	w := httptest.NewRecorder()
	req, _ := http.NewRequest(http.MethodGet, "/api/v1/stocks/005930/orderbook", nil)
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp apiResp
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}

	var obResp domain.OrderbookResponse
	if err := json.Unmarshal(resp.Result, &obResp); err != nil {
		t.Fatalf("failed to parse result: %v", err)
	}

	if obResp.Ticker != "005930" || obResp.CurrentPrice != 80550 || obResp.ChangeRate != 1.25 || obResp.AskPrice1 != 80600 {
		t.Errorf("unexpected orderbook response: %+v", obResp)
	}
}

func TestGetOrderbook_FallbackToInfoKey(t *testing.T) {
	h, _, mr := newTestComponents(t)
	defer mr.Close()

	// stocks:current 없이 stocks:info 로 currentPrice/changeRate fallback
	obData := `{"ticker":"005930","name":"삼성전자","askPrice1":80600,"askVolume1":15400,"bidPrice1":80500,"bidVolume1":32000}`
	mr.Set("stocks:orderbook:005930", obData)
	mr.HSet("stocks:info:005930", "currentPrice", "79900")
	mr.HSet("stocks:info:005930", "changeRate", "0.50")

	r := gin.New()
	r.GET("/api/v1/stocks/:ticker/orderbook", h.GetOrderbook)

	w := httptest.NewRecorder()
	req, _ := http.NewRequest(http.MethodGet, "/api/v1/stocks/005930/orderbook", nil)
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp apiResp
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}

	var obResp domain.OrderbookResponse
	if err := json.Unmarshal(resp.Result, &obResp); err != nil {
		t.Fatalf("failed to parse result: %v", err)
	}

	if obResp.CurrentPrice != 79900 {
		t.Errorf("expected currentPrice=79900 from info fallback, got %v", obResp.CurrentPrice)
	}
	if obResp.ChangeRate != 0.50 {
		t.Errorf("expected changeRate=0.50 from info fallback, got %v", obResp.ChangeRate)
	}
}

func TestGetOrderbook_NotFound(t *testing.T) {
	h, _, mr := newTestComponents(t)
	defer mr.Close()

	r := gin.New()
	r.GET("/api/v1/stocks/:ticker/orderbook", h.GetOrderbook)

	w := httptest.NewRecorder()
	req, _ := http.NewRequest(http.MethodGet, "/api/v1/stocks/000000/orderbook", nil)
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d: %s", w.Code, w.Body.String())
	}
}

// ─── GetTickSnapshot 핸들러 테스트 ──────────────────────────────────────────────

func TestGetTickSnapshot_Success(t *testing.T) {
	h, _, mr := newTestComponents(t)
	defer mr.Close()

	// 1. Info와 Current 데이터 셋업
	mr.HSet("stocks:info:005930", "name", "삼성전자")
	mr.HSet("stocks:info:005930", "currentPrice", "80000")
	mr.HSet("stocks:info:005930", "changeRate", "0.5")
	mr.HSet("stocks:info:005930", "accVolume", "1000000")

	mr.HSet("stocks:current:005930", "price", "80500")
	mr.HSet("stocks:current:005930", "change_rate", "1.25")
	mr.HSet("stocks:current:005930", "open", "80000")
	mr.HSet("stocks:current:005930", "high", "81000")
	mr.HSet("stocks:current:005930", "low", "79500")
	mr.HSet("stocks:current:005930", "trade_vol", "500")
	mr.HSet("stocks:current:005930", "acc_vol", "1500000")

	r := gin.New()
	r.GET("/api/v1/stocks/:ticker", h.GetTickSnapshot)

	w := httptest.NewRecorder()
	req, _ := http.NewRequest(http.MethodGet, "/api/v1/stocks/005930", nil)
	r.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", w.Code, w.Body.String())
	}

	var resp apiResp
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatalf("failed to parse response: %v", err)
	}

	if !resp.IsSuccess {
		t.Error("expected isSuccess=true")
	}

	var snap domain.TickSnapshotResponse
	if err := json.Unmarshal(resp.Result, &snap); err != nil {
		t.Fatalf("failed to parse result: %v", err)
	}

	if snap.Ticker != "005930" || snap.CurrentPrice != 80500 || snap.ChangeRate != 1.25 || snap.TradeVolume != 500 || snap.AccVolume != 1500000 {
		t.Errorf("unexpected tick snapshot response: %+v", snap)
	}
}

func TestGetTickSnapshot_NotFound(t *testing.T) {
	h, _, mr := newTestComponents(t)
	defer mr.Close()

	r := gin.New()
	r.GET("/api/v1/stocks/:ticker", h.GetTickSnapshot)

	w := httptest.NewRecorder()
	req, _ := http.NewRequest(http.MethodGet, "/api/v1/stocks/999999", nil)
	r.ServeHTTP(w, req)

	if w.Code != http.StatusNotFound {
		t.Errorf("expected 404, got %d: %s", w.Code, w.Body.String())
	}
}

