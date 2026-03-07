package handler

import (
	"net/http"
	"strconv"

	"github.com/gin-gonic/gin"
	"market-server/internal/domain"
	"market-server/internal/service"
	"market-server/pkg/response"
)

type StockHandler struct {
	svc *service.StockService
}

func NewStockHandler(svc *service.StockService) *StockHandler {
	return &StockHandler{svc: svc}
}

// GetStockList GET /api/v1/stocks
// 쿼리 파라미터:
//   - limit    : 조회 개수 (1~100, 기본값 50)
//   - rankType : 순위 기준 (VOLUME, 기본값 VOLUME)
func (h *StockHandler) GetStockList(c *gin.Context) {
	limitStr := c.DefaultQuery("limit", "40")
	limit, err := strconv.ParseInt(limitStr, 10, 64)
	if err != nil || limit < 1 || limit > 40 {
		c.JSON(http.StatusBadRequest, response.Fail("STOCK-400", "limit은 1~40 사이의 정수여야 합니다."))
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
func (h *StockHandler) GetCandles(c *gin.Context) {
	ticker := c.Param("ticker")
	if ticker == "" {
		c.JSON(http.StatusBadRequest, response.Fail("STOCK-400", "종목코드가 필요합니다."))
		return
	}

	interval := c.DefaultQuery("interval", "D")
	limitStr := c.DefaultQuery("limit", "50")
	limit, err := strconv.ParseInt(limitStr, 10, 64)
	if err != nil || limit < 1 {
		c.JSON(http.StatusBadRequest, response.Fail("STOCK-400", "limit은 1 이상의 정수여야 합니다."))
		return
	}

	candles, err := h.svc.GetCandles(c.Request.Context(), ticker, interval, limit)
	if err != nil {
		c.JSON(http.StatusInternalServerError, response.Fail("STOCK-500", "캔들 데이터 조회 중 오류가 발생했습니다."))
		return
	}

	c.JSON(http.StatusOK, response.OK(candles))
}
