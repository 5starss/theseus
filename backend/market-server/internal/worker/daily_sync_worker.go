package worker

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strconv"
	"time"

	"market-server/internal/domain"
	"market-server/internal/repository"
	"market-server/pkg/kis"
)

// DailySyncWorker KIS OpenAPI를 이용해 과거 일봉(1d) 데이터를 DB에 동기화(Backfill)한다.
type DailySyncWorker struct {
	kisClient *kis.Client
	stockRepo *repository.StockRepository
}

func NewDailySyncWorker(kc *kis.Client, repo *repository.StockRepository) *DailySyncWorker {
	return &DailySyncWorker{
		kisClient: kc,
		stockRepo: repo,
	}
}

// SyncPastDailyCandles 탑 40 종목에 대해 KIS OpenAPI로 최근 30일치 일봉 데이터를 가져와 DB에 저장한다.
func (w *DailySyncWorker) SyncPastDailyCandles(ctx context.Context) {
	log.Println("[DailySyncWorker] Starting past daily candles sync...")
	
	now := time.Now()
	// 최근 30영업일 조회를 위해 대략 45일 전부터 현재까지 요청
	startDate := now.AddDate(0, 0, -45).Format("20060102")
	endDate := now.Format("20060102")

	for ticker, name := range Top40Stocks {
		var err error
		// KIS API가 일시적으로 500을 반환하는 경우를 대비해 최대 3회 재시도
		for attempt := 1; attempt <= 3; attempt++ {
			err = w.syncTickerDaily(ctx, ticker, name, startDate, endDate)
			if err == nil {
				break
			}
			if attempt < 3 {
				log.Printf("[DailySyncWorker] Retry %d/3 for %s (%s): %v", attempt, ticker, name, err)
				time.Sleep(500 * time.Millisecond * time.Duration(attempt))
			}
		}
		if err != nil {
			log.Printf("[DailySyncWorker] Failed to sync %s (%s): %v", ticker, name, err)
		}
		// KIS API Rate Limit 고려 딜레이 (100ms → 200ms로 증가)
		time.Sleep(200 * time.Millisecond)
	}

	log.Println("[DailySyncWorker] Past daily candles sync completed.")
}

// StartDailyCloseScheduler 매일 장 마감 후(15:35 KST) 오늘자 일봉을 재동기화하는 스케줄러를 시작한다.
// KIS API에 종가가 확정 반영될 시간을 고려하여 15:30이 아닌 15:35에 트리거한다.
func (w *DailySyncWorker) StartDailyCloseScheduler(ctx context.Context) {
	const triggerHour = 15
	const triggerMin = 35

	kst, _ := time.LoadLocation("Asia/Seoul")

	// 다음 트리거 시각을 계산한다.
	calcNext := func() time.Time {
		now := time.Now().In(kst)
		next := time.Date(now.Year(), now.Month(), now.Day(), triggerHour, triggerMin, 0, 0, kst)
		if now.After(next) {
			next = next.AddDate(0, 0, 1) // 이미 지났으면 내일
		}
		return next
	}

	next := calcNext()
	log.Printf("[DailySyncWorker] Daily close scheduler started, next trigger at %s", next.Format("2006-01-02 15:04:05"))

	for {
		select {
		case <-time.After(time.Until(next)):
			w.syncTodayDailyCandles(ctx)
			next = calcNext()
			log.Printf("[DailySyncWorker] Next daily close sync scheduled at %s", next.Format("2006-01-02 15:04:05"))
		case <-ctx.Done():
			log.Println("[DailySyncWorker] Daily close scheduler stopped.")
			return
		}
	}
}

// syncTodayDailyCandles 오늘 날짜만을 대상으로 Top40 종목의 일봉을 KIS API에서 가져와 DB에 확정 저장한다.
func (w *DailySyncWorker) syncTodayDailyCandles(ctx context.Context) {
	log.Println("[DailySyncWorker] Starting today's daily candle sync (post-market close)...")

	kst, _ := time.LoadLocation("Asia/Seoul")
	today := time.Now().In(kst).Format("20060102")

	for ticker, name := range Top40Stocks {
		var err error
		for attempt := 1; attempt <= 3; attempt++ {
			err = w.syncTickerDaily(ctx, ticker, name, today, today)
			if err == nil {
				break
			}
			if attempt < 3 {
				log.Printf("[DailySyncWorker] Retry %d/3 for %s (%s) [today sync]: %v", attempt, ticker, name, err)
				time.Sleep(500 * time.Millisecond * time.Duration(attempt))
			}
		}
		if err != nil {
			log.Printf("[DailySyncWorker] Failed to sync today's candle for %s (%s): %v", ticker, name, err)
		}
		time.Sleep(200 * time.Millisecond) // KIS API Rate Limit
	}

	log.Println("[DailySyncWorker] Today's daily candle sync completed.")
}

type kisDailyChartResponse struct {
	Output2 []struct {
		StckBsopDate string `json:"stck_bsop_date"` // 영업일자
		StckOprc     string `json:"stck_oprc"`      // 시가
		StckHgpr     string `json:"stck_hgpr"`      // 고가
		StckLwpr     string `json:"stck_lwpr"`      // 저가
		StckClpr     string `json:"stck_clpr"`      // 종가
		AcmlVol      string `json:"acml_vol"`       // 누적거래량
	} `json:"output2"`
	Msg1 string `json:"msg1"`
}

func (w *DailySyncWorker) syncTickerDaily(ctx context.Context, ticker, name, startDate, endDate string) error {
	path := "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
	
	headers := map[string]string{
		"tr_id": "FHKST03010100", // 국내주식 기간별 시세 (일/주/월/년)
	}
	
	query := map[string]string{
		"FID_COND_MRKT_DIV_CODE": "J", // J: 주식
		"FID_INPUT_ISCD":         ticker,
		"FID_INPUT_DATE_1":       startDate,
		"FID_INPUT_DATE_2":       endDate,
		"FID_PERIOD_DIV_CODE":    "D", // D: 일봉
		"FID_ORG_ADJ_PRC":        "0", // 0: 수정주가
	}

	respData, err := w.kisClient.DoRequest(ctx, "GET", path, headers, query)
	if err != nil {
		return fmt.Errorf("api request: %w", err)
	}

	var parsedResp kisDailyChartResponse
	if err := json.Unmarshal(respData, &parsedResp); err != nil {
		return fmt.Errorf("json unmarshal: %w", err)
	}

	var candles []domain.Candle
	for _, item := range parsedResp.Output2 {
		if item.StckBsopDate == "" || len(item.StckBsopDate) != 8 {
			continue // 유효하지 않은 응답 포맷 패스
		}
		
		// KIS API 응답 YYYYMMDD -> DB DATE 포맷 YYYY-MM-DD 로 변환
		parsedDate, err := time.Parse("20060102", item.StckBsopDate)
		if err != nil {
			log.Printf("[DailySyncWorker] date parse error: %v", err)
			continue
		}
		formattedDate := parsedDate.Format("2006-01-02")

		open, _ := strconv.ParseInt(item.StckOprc, 10, 64)
		high, _ := strconv.ParseInt(item.StckHgpr, 10, 64)
		low, _ := strconv.ParseInt(item.StckLwpr, 10, 64)
		closePrice, _ := strconv.ParseInt(item.StckClpr, 10, 64)
		volume, _ := strconv.ParseInt(item.AcmlVol, 10, 64)

		candles = append(candles, domain.Candle{
			Timestamp: formattedDate, // YYYY-MM-DD format
			Open:      open,
			High:      high,
			Low:       low,
			Close:     closePrice,
			Volume:    volume,
		})
	}

	if len(candles) > 0 {
		if err := w.stockRepo.BulkInsertCandlesSlice(ctx, candles, ticker, domain.IntervalDay); err != nil {
			return fmt.Errorf("db insert: %w", err)
		}
		log.Printf("[DailySyncWorker] Synced %d daily candles for %s", len(candles), ticker)
	}

	return nil
}
