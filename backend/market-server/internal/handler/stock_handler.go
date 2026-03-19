package handler

import (
	"net/http"
	"strconv"

	"market-server/internal/domain"
	"market-server/internal/service"
	"market-server/pkg/response"

	"github.com/gin-gonic/gin"
)

type StockHandler struct {
	svc *service.StockService
}

func NewStockHandler(svc *service.StockService) *StockHandler {
	return &StockHandler{svc: svc}
}

// GetStockList GET /api/v1/stocks
// 쿼리 파라미터:
//   - limit    : 조회 개수 (1~100, 기본값 100)
//   - rankType : 순위 기준 (VOLUME, 기본값 VOLUME)
func (h *StockHandler) GetStockList(c *gin.Context) {
	limitStr := c.DefaultQuery("limit", "100")
	limit, err := strconv.ParseInt(limitStr, 10, 64)
	if err != nil || limit < 1 || limit > 100 {
		c.JSON(http.StatusBadRequest, response.Fail("STOCK-400", "limit은 1~100 사이의 정수여야 합니다."))
		return
	}

	rankTypeStr := c.DefaultQuery("rankType", string(domain.RankTypeVolume))
	rankType := domain.RankType(rankTypeStr)
	if rankType != domain.RankTypeVolume {
		c.JSON(http.StatusBadRequest, response.Fail("STOCK-400", "지원하지 않는 rankType입니다."))
		return
	}

	stocks, err := h.svc.GetTopStocks(c.Request.Context(), limit, rankType)
	if err != nil {
		c.JSON(http.StatusInternalServerError, response.Fail("STOCK-500", "종목 조회 중 오류가 발생했습니다."))
		return
	}

	// []*domain.Stock → []domain.Stock 변환 (JSON 직렬화 일관성)
	result := make([]domain.Stock, 0, len(stocks))
	for _, s := range stocks {
		result = append(result, *s)
	}

	c.JSON(http.StatusOK, response.OK(result))
}

// GetCandles GET /api/v1/stocks/:ticker/candles
// 쿼리 파라미터:
//   - interval : 간격 (D, W, M 등, 기본값 D)
//   - limit    : 캔들 개수 (1~1000, 기본값 50)
//   - endTime  : 특정 시간 이전의 데이터 조회용 커서 (형식: 2006-01-02T15:04:05, 옵션)
func (h *StockHandler) GetCandles(c *gin.Context) {
	ticker := c.Param("ticker")
	if ticker == "" {
		c.JSON(http.StatusBadRequest, response.Fail("STOCK-400", "종목코드가 필요합니다."))
		return
	}

	intervalStr := c.DefaultQuery("interval", "D")

	// Normalize interval based on API_SPEC to internal domain format
	var interval domain.Interval
	switch intervalStr {
	case "D", "d", "day", "1d":
		interval = domain.IntervalDay
	case "1", "1M", "1m", "min":
		interval = domain.IntervalMinute
	default:
		// 지원하지 않는 interval은 일단 일봉으로 Fallback 하거나 에러 리턴
		interval = domain.IntervalDay
	}

	limitStr := c.DefaultQuery("limit", "50")
	limit, err := strconv.ParseInt(limitStr, 10, 64)
	if err != nil || limit < 1 {
		c.JSON(http.StatusBadRequest, response.Fail("STOCK-400", "limit은 1 이상의 정수여야 합니다."))
		return
	}

	endTime := c.Query("endTime")

	candles, err := h.svc.GetCandles(c.Request.Context(), ticker, interval, limit, endTime)
	if err != nil {
		c.JSON(http.StatusInternalServerError, response.Fail("STOCK-500", "캔들 데이터 조회 중 오류가 발생했습니다."))
		return
	}

	c.JSON(http.StatusOK, response.OK(candles))
}

// GetOrderbook GET /api/v1/stocks/:ticker/orderbook
// 호가창 스냅샷(현재가 포함) 조회 API
func (h *StockHandler) GetOrderbook(c *gin.Context) {
	ticker := c.Param("ticker")
	if ticker == "" {
		c.JSON(http.StatusBadRequest, response.Fail("STOCK-400", "종목코드가 필요합니다."))
		return
	}

	ob, err := h.svc.GetOrderbook(c.Request.Context(), ticker)
	if err != nil {
		c.JSON(http.StatusInternalServerError, response.Fail("STOCK-500", "호가창 스냅샷 조회 중 오류가 발생했습니다."))
		return
	}

	if ob == nil {
		c.JSON(http.StatusNotFound, response.Fail("STOCK-404", "호가창 스냅샷 데이터가 존재하지 않습니다."))
		return
	}

	c.JSON(http.StatusOK, response.OK(ob))
}

// GetTickSnapshot GET /api/v1/stocks/:ticker
// 상세 종목 실시간 요약 (TICK 스냅샷) 조회 API
func (h *StockHandler) GetTickSnapshot(c *gin.Context) {
	ticker := c.Param("ticker")
	if ticker == "" {
		c.JSON(http.StatusBadRequest, response.Fail("STOCK-400", "종목코드가 필요합니다."))
		return
	}

	snap, err := h.svc.GetTickSnapshot(c.Request.Context(), ticker)
	if err != nil {
		c.JSON(http.StatusInternalServerError, response.Fail("STOCK-500", "TICK 스냅샷 조회 중 오류가 발생했습니다."))
		return
	}

	if snap == nil {
		c.JSON(http.StatusNotFound, response.Fail("STOCK-404", "해당 종목의 TICK 스냅샷 데이터가 존재하지 않습니다."))
		return
	}

	c.JSON(http.StatusOK, response.OK(snap))
}
