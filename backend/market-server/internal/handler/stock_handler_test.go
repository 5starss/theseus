package handler

import (
	"encoding/json"
	"fmt"
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
	svc := service.NewStockService(repo, nil)
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
	h, _, mr := newTestComponents(t)
	defer mr.Close()

	candles := []domain.Candle{
		{Timestamp: "20240101", Open: 70000, High: 71000, Low: 69000, Close: 70500, Volume: 1000000},
		{Timestamp: "20240102", Open: 70500, High: 72000, Low: 70000, Close: 71500, Volume: 1200000},
	}
	b, _ := json.Marshal(candles)
	mr.Set(fmt.Sprintf("stocks:candles:%s:%s", "005930", "D"), string(b))

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
	if result[0].Timestamp != "20240101" || result[0].Close != 70500 {
		t.Errorf("unexpected first candle: %+v", result[0])
	}
}

func TestGetCandles_DefaultInterval(t *testing.T) {
	h, _, mr := newTestComponents(t)
	defer mr.Close()

	// interval 미지정 시 "D"로 캐시에서 조회해야 함
	candles := []domain.Candle{{Timestamp: "20240101", Close: 70500}}
	b, _ := json.Marshal(candles)
	mr.Set(fmt.Sprintf("stocks:candles:%s:%s", "005930", "D"), string(b))

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

func TestGetStockList_InvalidLimit_Over40(t *testing.T) {
	h, _, mr := newTestComponents(t)
	defer mr.Close()

	r := newRouter(h)
	w := httptest.NewRecorder()
	req, _ := http.NewRequest(http.MethodGet, "/api/v1/stocks?limit=41", nil)
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
