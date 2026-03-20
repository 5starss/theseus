package repository

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strconv"
	"time"

	"market-server/internal/domain"

	"github.com/redis/go-redis/v9"
)

const (
	rankVolumeKey   = "stocks:rank:volume"   // Sorted Set: score=거래량, member=종목코드
	stockInfoKeyFmt = "stocks:info:%s"       // Hash: 종목 상세 정보
	candlesKeyFmt   = "stocks:candles:%s:%s" // String (JSON): 캔들 데이터 단기 캐시 (ticker, interval)
)

type StockRepository struct {
	rdb *redis.Client
	db  *sql.DB
}

func NewStockRepository(rdb *redis.Client, db *sql.DB) *StockRepository {
	return &StockRepository{rdb: rdb, db: db}
}

// GetTopByVolume Redis Sorted Set에서 거래량 상위 limit개 종목을 조회한다.
// ZREVRANGE → Pipeline MGET 순서로 두 번의 왕복으로 처리한다.
func (r *StockRepository) GetTopByVolume(ctx context.Context, limit int64) ([]*domain.Stock, error) {
	// 1단계: Sorted Set에서 상위 종목코드 목록 조회 (내림차순)
	tickers, err := r.rdb.ZRevRange(ctx, rankVolumeKey, 0, limit-1).Result()
	if err != nil {
		return nil, fmt.Errorf("zrevrange failed: %w", err)
	}
	if len(tickers) == 0 {
		return []*domain.Stock{}, nil
	}

	// 2단계: Pipeline으로 종목 상세정보 일괄 조회 (HGETALL)
	pipe := r.rdb.Pipeline()
	cmds := make([]*redis.MapStringStringCmd, len(tickers))
	for i, ticker := range tickers {
		cmds[i] = pipe.HGetAll(ctx, fmt.Sprintf(stockInfoKeyFmt, ticker))
	}
	if _, err := pipe.Exec(ctx); err != nil && err != redis.Nil {
		return nil, fmt.Errorf("pipeline exec failed: %w", err)
	}

	stocks := make([]*domain.Stock, 0, len(tickers))
	for _, cmd := range cmds {
		val, err := cmd.Result()
		if err != nil || len(val) == 0 {
			continue // 개별 키 누락은 건너뜀
		}
		
		// Map을 파싱하여 Stock 객체로 변환
		currentPrice, _ := strconv.ParseInt(val["currentPrice"], 10, 64)
		changeRate, _ := strconv.ParseFloat(val["changeRate"], 64)
		accVolume, _ := strconv.ParseInt(val["accVolume"], 10, 64)

		stocks = append(stocks, &domain.Stock{
			Ticker:       val["ticker"],
			Name:         val["name"],
			CurrentPrice: currentPrice,
			ChangeRate:   changeRate,
			AccVolume:    accVolume,
		})
	}

	return stocks, nil
}

// GetAllStocks Redis Sorted Set에서 거래량을 기준으로 모든 종목 정보를 조회한다 (In-Memory 캐시용).
func (r *StockRepository) GetAllStocks(ctx context.Context) ([]*domain.Stock, error) {
	// 1단계: Sorted Set에서 전체 종목코드 목록 조회 (내림차순, -1은 전체를 의미)
	tickers, err := r.rdb.ZRevRange(ctx, rankVolumeKey, 0, -1).Result()
	if err != nil {
		return nil, fmt.Errorf("GetAllStocks zrevrange failed: %w", err)
	}
	if len(tickers) == 0 {
		return []*domain.Stock{}, nil
	}

	// 2단계: Pipeline으로 종목 상세정보 일괄 조회 (HGETALL)
	pipe := r.rdb.Pipeline()
	cmds := make([]*redis.MapStringStringCmd, len(tickers))
	for i, ticker := range tickers {
		cmds[i] = pipe.HGetAll(ctx, fmt.Sprintf(stockInfoKeyFmt, ticker))
	}
	if _, err := pipe.Exec(ctx); err != nil && err != redis.Nil {
		return nil, fmt.Errorf("GetAllStocks pipeline exec failed: %w", err)
	}

	stocks := make([]*domain.Stock, 0, len(tickers))
	for _, cmd := range cmds {
		val, err := cmd.Result()
		if err != nil || len(val) == 0 {
			continue
		}
		
		currentPrice, _ := strconv.ParseInt(val["currentPrice"], 10, 64)
		changeRate, _ := strconv.ParseFloat(val["changeRate"], 64)
		accVolume, _ := strconv.ParseInt(val["accVolume"], 10, 64)

		stocks = append(stocks, &domain.Stock{
			Ticker:       val["ticker"],
			Name:         val["name"],
			CurrentPrice: currentPrice,
			ChangeRate:   changeRate,
			AccVolume:    accVolume,
		})
	}

	return stocks, nil
}

// BulkUpsertStocks Pipeline으로 종목 정보와 거래량 순위를 일괄 저장한다.
// stocks:info:{ticker} ← Hash, stocks:rank:volume ← ZADD score=거래량
func (r *StockRepository) BulkUpsertStocks(ctx context.Context, stocks []*domain.Stock) error {
	pipe := r.rdb.Pipeline()

	for _, s := range stocks {
		key := fmt.Sprintf(stockInfoKeyFmt, s.Ticker)
		pipe.HSet(ctx, key, map[string]interface{}{
			"ticker":       s.Ticker,
			"name":         s.Name,
			"currentPrice": s.CurrentPrice,
			"changeRate":   s.ChangeRate,
			"accVolume":    s.AccVolume,
		})
		pipe.Expire(ctx, key, 24*time.Hour)
		pipe.ZAdd(ctx, rankVolumeKey, redis.Z{
			Score:  float64(s.AccVolume),
			Member: s.Ticker,
		})
	}
	// 랭킹 키 자체도 TTL 설정: 서비스 중단 시 stale 데이터가 영구 잔존하는 것을 방지
	pipe.Expire(ctx, rankVolumeKey, 24*time.Hour)

	if _, err := pipe.Exec(ctx); err != nil {
		return fmt.Errorf("bulk upsert pipeline exec failed: %w", err)
	}

	return nil
}

// GetCandlesFromCache Redis에서 캔들 데이터를 단기 캐시로 조회한다.
func (r *StockRepository) GetCandlesFromCache(ctx context.Context, ticker string, interval domain.Interval) ([]domain.Candle, error) {
	key := fmt.Sprintf(candlesKeyFmt, ticker, interval)
	
	vals, err := r.rdb.ZRevRange(ctx, key, 0, -1).Result()
	if err != nil {
		return nil, fmt.Errorf("redis zrevrange failed: %w", err)
	}
	if len(vals) == 0 {
		return nil, nil // Cache Miss
	}

	var candles []domain.Candle
	for _, val := range vals {
		var c domain.Candle
		if err := json.Unmarshal([]byte(val), &c); err == nil {
			candles = append(candles, c)
		}
	}
	return candles, nil
}

// SaveCandlesToCache Redis에 캔들 데이터를 적재시킨다. (TTL: 1분)
func (r *StockRepository) SaveCandlesToCache(ctx context.Context, ticker string, interval domain.Interval, candles []domain.Candle) error {
	key := fmt.Sprintf(candlesKeyFmt, ticker, interval)
	
	pipe := r.rdb.Pipeline()
	// 기존 데이터 지우고 새로 캐싱 (단기 캐시이므로)
	pipe.Del(ctx, key)
	
	for _, c := range candles {
		bytes, err := json.Marshal(c)
		if err != nil {
			continue
		}
		
		var score float64
		if interval == domain.IntervalDay {
			// MySQL DATE (2006-01-02)
			if t, err := time.Parse("2006-01-02", c.Timestamp); err == nil {
				score = float64(t.Unix())
			}
		} else {
			// MySQL DATETIME (2006-01-02 15:04:05)
			if t, err := time.Parse("2006-01-02 15:04:05", c.Timestamp); err == nil {
				score = float64(t.Unix())
			}
		}

		pipe.ZAdd(ctx, key, redis.Z{
			Score:  score,
			Member: string(bytes),
		})
	}
	
	pipe.Expire(ctx, key, 1*time.Minute)
	
	if _, err := pipe.Exec(ctx); err != nil {
		return fmt.Errorf("redis zadd pipeline failed: %w", err)
	}
	
	return nil
}

// GetCandlesFromDB MySQL에서 캔들 데이터를 조회한다.
func (r *StockRepository) GetCandlesFromDB(ctx context.Context, ticker string, interval domain.Interval, limit int64, endTime string) ([]domain.Candle, error) {
	var tableName, timeCol string
	if interval == domain.IntervalDay {
		tableName = "candle_1d"
		timeCol = "candle_date"
	} else if interval == domain.IntervalMinute {
		tableName = "candle_1m"
		timeCol = "candle_time"
	} else {
		return nil, fmt.Errorf("unsupported interval for db fetch: %s", interval)
	}

	var query string
	var args []interface{}

	if endTime != "" {
		query = fmt.Sprintf(`
			SELECT %s, open_price, high_price, low_price, close_price, volume
			FROM %s
			WHERE ticker = ? AND %s < ?
			ORDER BY %s DESC
			LIMIT ?
		`, timeCol, tableName, timeCol, timeCol)
		args = append(args, ticker, endTime, limit)
	} else {
		query = fmt.Sprintf(`
			SELECT %s, open_price, high_price, low_price, close_price, volume
			FROM %s
			WHERE ticker = ?
			ORDER BY %s DESC
			LIMIT ?
		`, timeCol, tableName, timeCol)
		args = append(args, ticker, limit)
	}

	rows, err := r.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("mysql query failed: %w", err)
	}
	defer rows.Close()

	var candles []domain.Candle
	for rows.Next() {
		var c domain.Candle
		var ts []byte // DB Driver 가 반환하는 date/datetime 문자열 처리
		
		if err := rows.Scan(&ts, &c.Open, &c.High, &c.Low, &c.Close, &c.Volume); err != nil {
			return nil, fmt.Errorf("rows scan failed: %w", err)
		}
		c.Timestamp = string(ts)
		candles = append(candles, c)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration failed: %w", err)
	}

	return candles, nil
}

// BulkInsertCandles 여러 종목의 캔들 데이터를 한 번의 다중 INSERT 처리로 DB에 적재한다.
func (r *StockRepository) BulkInsertCandles(ctx context.Context, candlesMap map[string]*domain.Candle, interval domain.Interval) error {
	if len(candlesMap) == 0 {
		return nil
	}

	var tableName, timeCol string
	if interval == domain.IntervalDay {
		tableName = "candle_1d"
		timeCol = "candle_date"
	} else if interval == domain.IntervalMinute {
		tableName = "candle_1m"
		timeCol = "candle_time"
	} else {
		return fmt.Errorf("unsupported interval for bulk insert: %s", interval)
	}

	query := fmt.Sprintf("INSERT INTO %s (ticker, %s, open_price, high_price, low_price, close_price, volume) VALUES ", tableName, timeCol)
	var args []interface{}

	i := 0
	for ticker, c := range candlesMap {
		if c == nil {
			continue
		}
		if i > 0 {
			query += ", "
		}
		query += "(?, ?, ?, ?, ?, ?, ?)"
		args = append(args, ticker, c.Timestamp, c.Open, c.High, c.Low, c.Close, c.Volume)
		i++
	}

	if i == 0 {
		return nil // 넣을 유효한 캔들이 없음
	}

	// 타임스탬프 중복 시 덮어쓰기 (ON DUPLICATE KEY UPDATE)
	query += " ON DUPLICATE KEY UPDATE open_price=VALUES(open_price), high_price=VALUES(high_price), low_price=VALUES(low_price), close_price=VALUES(close_price), volume=VALUES(volume)"

	_, err := r.db.ExecContext(ctx, query, args...)
	if err != nil {
		return fmt.Errorf("mysql bulk insert candles failed: %w", err)
	}

	return nil
}

// BulkInsertCandlesSlice 한 종목의 여러 캔들(과거 데이터)을 한 번에 DB에 적재한다.
func (r *StockRepository) BulkInsertCandlesSlice(ctx context.Context, candles []domain.Candle, ticker string, interval domain.Interval) error {
	if len(candles) == 0 {
		return nil
	}

	var tableName, timeCol string
	if interval == domain.IntervalDay {
		tableName = "candle_1d"
		timeCol = "candle_date"
	} else if interval == domain.IntervalMinute {
		tableName = "candle_1m"
		timeCol = "candle_time"
	} else {
		return fmt.Errorf("unsupported interval for bulk insert slice: %s", interval)
	}

	query := fmt.Sprintf("INSERT INTO %s (ticker, %s, open_price, high_price, low_price, close_price, volume) VALUES ", tableName, timeCol)
	var args []interface{}

	for i, c := range candles {
		if i > 0 {
			query += ", "
		}
		query += "(?, ?, ?, ?, ?, ?, ?)"
		args = append(args, ticker, c.Timestamp, c.Open, c.High, c.Low, c.Close, c.Volume)
	}

	// 타임스탬프 중복 시 덮어쓰기
	query += " ON DUPLICATE KEY UPDATE open_price=VALUES(open_price), high_price=VALUES(high_price), low_price=VALUES(low_price), close_price=VALUES(close_price), volume=VALUES(volume)"

	_, err := r.db.ExecContext(ctx, query, args...)
	if err != nil {
		return fmt.Errorf("mysql bulk insert candles slice failed: %w", err)
	}

	return nil
}

// GetOrderbookSnapshot Redis에서 호가창 스냅샷 및 현재가 정보를 조회하여 반환한다.
func (r *StockRepository) GetOrderbookSnapshot(ctx context.Context, ticker string) (*domain.OrderbookResponse, error) {
	// 조회할 키
	orderbookKey := "stocks:orderbook:" + ticker
	currentKey := "stocks:current:" + ticker

	// 1. Pipeline을 통한 동시 조회
	pipe := r.rdb.Pipeline()
	obCmd := pipe.Get(ctx, orderbookKey)
	currCmd := pipe.HGetAll(ctx, currentKey)

	_, err := pipe.Exec(ctx)
	if err != nil && err != redis.Nil {
		return nil, fmt.Errorf("pipeline exec failed: %w", err)
	}

	obJSON, err := obCmd.Result()
	if err == redis.Nil {
		return nil, nil // 호가 데이터 없음
	} else if err != nil {
		return nil, fmt.Errorf("redis get orderbook failed: %w", err)
	}

	currHash, err := currCmd.Result()
	if err != nil && err != redis.Nil {
		return nil, fmt.Errorf("redis hgetall current failed: %w", err)
	}

	// 2. 파싱 및 병합
	var resp domain.OrderbookResponse
	if err := json.Unmarshal([]byte(obJSON), &resp); err != nil {
		return nil, fmt.Errorf("json unmarshal orderbook failed: %w", err)
	}

	// current가 존재하면 덮어쓰기 (워커가 저장한 실시간 체결가)
	if len(currHash) > 0 {
		if p, err := strconv.ParseFloat(currHash["price"], 64); err == nil {
			resp.CurrentPrice = p
		}
		if cr, err := strconv.ParseFloat(currHash["change_rate"], 64); err == nil {
			resp.ChangeRate = cr
		}
	} else {
		// Fallback: stocks:info:{ticker} 조회 
		infoCmd := r.rdb.HGetAll(ctx, fmt.Sprintf(stockInfoKeyFmt, ticker))
		infoHash, err := infoCmd.Result()
		if err == nil && len(infoHash) > 0 {
			if p, err := strconv.ParseFloat(infoHash["currentPrice"], 64); err == nil {
				resp.CurrentPrice = p
			}
			if cr, err := strconv.ParseFloat(infoHash["changeRate"], 64); err == nil {
				resp.ChangeRate = cr
			}
		}
	}

	return &resp, nil
}

// GetTickSnapshot Redis에서 상세 종목 실시간 체결 스냅샷 정보를 조회하여 반환한다.
func (r *StockRepository) GetTickSnapshot(ctx context.Context, ticker string) (*domain.TickSnapshotResponse, error) {
	currentKey := "stocks:current:" + ticker
	infoKey := fmt.Sprintf(stockInfoKeyFmt, ticker)

	// 1. Pipeline으로 current 와 info 동시 조회
	pipe := r.rdb.Pipeline()
	currCmd := pipe.HGetAll(ctx, currentKey)
	infoCmd := pipe.HGetAll(ctx, infoKey)

	_, err := pipe.Exec(ctx)
	if err != nil && err != redis.Nil {
		return nil, fmt.Errorf("pipeline exec failed: %w", err)
	}

	currHash, err := currCmd.Result()
	if err != nil && err != redis.Nil {
		return nil, fmt.Errorf("redis hgetall current failed: %w", err)
	}

	infoHash, err := infoCmd.Result()
	if err != nil && err != redis.Nil {
		return nil, fmt.Errorf("redis hgetall info failed: %w", err)
	}

	if len(currHash) == 0 && len(infoHash) == 0 {
		return nil, nil // 데이터 없음
	}

	var resp domain.TickSnapshotResponse
	resp.Ticker = ticker

	// Helper 함수들
	parseFloat := func(s string) float64 {
		val, _ := strconv.ParseFloat(s, 64)
		return val
	}
	parseInt := func(s string) int64 {
		val, _ := strconv.ParseInt(s, 10, 64)
		return val
	}

	// 2. Info 기준 기본 데이터 설정 (정적인 데이터 + 초기 데이터)
	if len(infoHash) > 0 {
		resp.Name = infoHash["name"]
		resp.CurrentPrice = parseFloat(infoHash["currentPrice"])
		resp.ChangeRate = parseFloat(infoHash["changeRate"])
		resp.AccVolume = parseInt(infoHash["accVolume"])
	}

	// 3. Current(실시간) 기준 데이터 덮어쓰기 및 추가 데이터 병합
	if len(currHash) > 0 {
		if name, ok := currHash["name"]; ok && name != "" {
			resp.Name = name
		}
		if price, ok := currHash["price"]; ok {
			resp.CurrentPrice = parseFloat(price)
		}
		if cr, ok := currHash["change_rate"]; ok {
			resp.ChangeRate = parseFloat(cr)
		}
		if open, ok := currHash["open"]; ok {
			resp.OpenPrice = parseFloat(open)
		}
		if high, ok := currHash["high"]; ok {
			resp.HighPrice = parseFloat(high)
		}
		if low, ok := currHash["low"]; ok {
			resp.LowPrice = parseFloat(low)
		}
		if tradeVol, ok := currHash["trade_vol"]; ok {
			resp.TradeVolume = parseInt(tradeVol)
		}
		if accVol, ok := currHash["acc_vol"]; ok {
			resp.AccVolume = parseInt(accVol)
		}
	}

	return &resp, nil
}
