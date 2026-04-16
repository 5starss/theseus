package repository

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"testing"
	"time"

	"market-server/internal/domain"

	_ "github.com/go-sql-driver/mysql"
)

// ─── MySQL 통합 테스트 헬퍼 ───────────────────────────────────────────────────

func getEnvOrDefaultTest(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

// newTestDB MySQL 연결을 반환한다. DB 미실행 시 t.Skip()으로 건너뛴다.
func newTestDB(t *testing.T) *sql.DB {
	t.Helper()
	user := getEnvOrDefaultTest("DB_USER", "root")
	pass := os.Getenv("DB_PASSWORD")
	host := getEnvOrDefaultTest("DB_HOST", "localhost")
	port := getEnvOrDefaultTest("DB_PORT", "3306")
	dbName := getEnvOrDefaultTest("DB_NAME", "stock_db")

	dsn := fmt.Sprintf("%s:%s@tcp(%s:%s)/%s?charset=utf8mb4",
		user, pass, host, port, dbName)

	db, err := sql.Open("mysql", dsn)
	if err != nil {
		t.Skipf("MySQL 연결 불가 (DSN 파싱 실패): %v", err)
	}
	if err := db.Ping(); err != nil {
		t.Skipf("MySQL Ping 실패 (DB가 실행 중인지 확인): %v", err)
	}
	return db
}

// newTestRepoWithDB miniredis(Redis) + 실제 MySQL을 사용하는 리포지토리 반환.
func newTestRepoWithDB(t *testing.T) (*StockRepository, *sql.DB, func()) {
	t.Helper()
	miniRepo, mr := newTestRepo(t) // miniredis
	db := newTestDB(t)
	repo := NewStockRepository(miniRepo.rdb, db)

	cleanup := func() {
		mr.Close()
		db.Close()
	}
	return repo, db, cleanup
}

// insertTestStockMeta FK 제약을 만족시키기 위해 테스트용 stock_meta 행을 삽입한다.
// user requested to keep only ticker and name.
func insertTestStockMeta(t *testing.T, db *sql.DB, tickers []string) {
	t.Helper()
	for _, ticker := range tickers {
		_, err := db.Exec(
			"INSERT IGNORE INTO stock_meta (ticker, name) VALUES (?, ?)",
			ticker, "테스트종목_"+ticker,
		)
		if err != nil {
			t.Fatalf("stock_meta INSERT 실패 (ticker=%s): %v", ticker, err)
		}
	}
}

// cleanupTestData stock_meta에서 삭제하면 FK CASCADE로 candle_1m/candle_1d도 같이 삭제된다.
func cleanupTestData(t *testing.T, db *sql.DB, tickers []string) {
	t.Helper()
	for _, ticker := range tickers {
		if _, err := db.Exec("DELETE FROM stock_meta WHERE ticker = ?", ticker); err != nil {
			t.Logf("[cleanup] stock_meta 삭제 실패 (ticker=%s): %v", ticker, err)
		}
	}
}



// ─── BulkInsertCandles (map 기반, 1분봉 → candle_1m) 통합 테스트 ──────────────

// TestBulkInsertCandles_SingleTicker_InsertsCorrectly 단일 종목 1분봉 INSERT 검증
func TestBulkInsertCandles_SingleTicker_InsertsCorrectly(t *testing.T) {
	repo, db, teardown := newTestRepoWithDB(t)
	defer teardown()

	ticker := "ZTST01"
	insertTestStockMeta(t, db, []string{ticker})
	defer cleanupTestData(t, db, []string{ticker})

	// candle_time: DATETIME 형식
	ts := time.Now().Truncate(time.Minute).Format("2006-01-02 15:04:00")

	candlesMap := map[string]*domain.Candle{
		ticker: {
			Timestamp: ts,
			Open:      80000,
			High:      81500,
			Low:       79000,
			Close:     80500,
			Volume:    1000,
		},
	}

	ctx := context.Background()
	if err := repo.BulkInsertCandles(ctx, candlesMap, domain.IntervalMinute); err != nil {
		t.Fatalf("BulkInsertCandles 실패: %v", err)
	}

	// SELECT로 검증
	var openP, highP, lowP, closeP, volume int64
	err := db.QueryRowContext(ctx,
		"SELECT open_price, high_price, low_price, close_price, volume FROM candle_1m WHERE ticker=? AND candle_time=?",
		ticker, ts,
	).Scan(&openP, &highP, &lowP, &closeP, &volume)
	if err != nil {
		t.Fatalf("INSERT 후 SELECT 실패: %v", err)
	}

	checks := []struct {
		field string
		want  int64
		got   int64
	}{
		{"open_price", 80000, openP},
		{"high_price", 81500, highP},
		{"low_price", 79000, lowP},
		{"close_price", 80500, closeP},
		{"volume", 1000, volume},
	}
	for _, c := range checks {
		if c.got != c.want {
			t.Errorf("%s: want %d, got %d", c.field, c.want, c.got)
		}
	}
}

// TestBulkInsertCandles_MultipleTickers_InsertsAll 다수 종목 bulk insert — 모두 삽입되어야 함
func TestBulkInsertCandles_MultipleTickers_InsertsAll(t *testing.T) {
	repo, db, teardown := newTestRepoWithDB(t)
	defer teardown()

	tickers := []string{"ZTST11", "ZTST12", "ZTST13", "ZTST14", "ZTST15"}
	insertTestStockMeta(t, db, tickers)
	defer cleanupTestData(t, db, tickers)

	ts := time.Now().Truncate(time.Minute).Format("2006-01-02 15:04:00")
	candlesMap := make(map[string]*domain.Candle)
	for i, tk := range tickers {
		candlesMap[tk] = &domain.Candle{
			Timestamp: ts,
			Open:      int64(70000 + i*1000), High: int64(71000 + i*1000),
			Low:       int64(69000 + i*1000), Close: int64(70500 + i*1000),
			Volume:    int64(100000 + i*10000),
		}
	}

	ctx := context.Background()
	if err := repo.BulkInsertCandles(ctx, candlesMap, domain.IntervalMinute); err != nil {
		t.Fatalf("BulkInsertCandles 실패: %v", err)
	}

	for _, tk := range tickers {
		var count int
		_ = db.QueryRowContext(ctx,
			"SELECT COUNT(*) FROM candle_1m WHERE ticker=?", tk,
		).Scan(&count)
		if count == 0 {
			t.Errorf("종목 %s의 1분봉이 DB에 없음", tk)
		}
	}
}

// TestBulkInsertCandles_EmptyMap_IsNoOp 빈 맵은 에러 없이 종료한다.
func TestBulkInsertCandles_EmptyMap_IsNoOp(t *testing.T) {
	repo, _, teardown := newTestRepoWithDB(t)
	defer teardown()

	if err := repo.BulkInsertCandles(context.Background(), map[string]*domain.Candle{}, domain.IntervalMinute); err != nil {
		t.Errorf("빈 맵에서 에러 반환: %v", err)
	}
}

// TestBulkInsertCandles_NilCandleInMap_IsSkipped map 값이 nil인 항목은 건너뛴다.
func TestBulkInsertCandles_NilCandleInMap_IsSkipped(t *testing.T) {
	repo, db, teardown := newTestRepoWithDB(t)
	defer teardown()

	tickers := []string{"ZNIL01", "ZNIL02"}
	insertTestStockMeta(t, db, tickers)
	defer cleanupTestData(t, db, tickers)

	ts := time.Now().Truncate(time.Minute).Format("2006-01-02 15:04:00")
	ctx := context.Background()
	candlesMap := map[string]*domain.Candle{
		"ZNIL01": nil, // nil 캔들 → 건너뜀
		"ZNIL02": {Timestamp: ts, Open: 50000, High: 51000, Low: 49000, Close: 50500, Volume: 200},
	}

	if err := repo.BulkInsertCandles(ctx, candlesMap, domain.IntervalMinute); err != nil {
		t.Fatalf("nil 캔들 포함 맵 처리 실패: %v", err)
	}

	var count int
	_ = db.QueryRowContext(ctx, "SELECT COUNT(*) FROM candle_1m WHERE ticker='ZNIL01'").Scan(&count)
	if count != 0 {
		t.Errorf("nil 캔들(ZNIL01)은 INSERT되지 않아야 한다, count=%d", count)
	}

	_ = db.QueryRowContext(ctx, "SELECT COUNT(*) FROM candle_1m WHERE ticker='ZNIL02'").Scan(&count)
	if count == 0 {
		t.Errorf("정상 캔들(ZNIL02)은 INSERT되어야 한다")
	}
}

// TestBulkInsertCandles_DuplicateTime_UpdatesExisting 동일 (ticker, candle_time) → ON DUPLICATE KEY UPDATE
func TestBulkInsertCandles_DuplicateTime_UpdatesExisting(t *testing.T) {
	repo, db, teardown := newTestRepoWithDB(t)
	defer teardown()

	ticker := "ZDUP01"
	insertTestStockMeta(t, db, []string{ticker})
	defer cleanupTestData(t, db, []string{ticker})

	ts := time.Now().Truncate(time.Minute).Format("2006-01-02 15:04:00")
	ctx := context.Background()

	// 1차 INSERT
	if err := repo.BulkInsertCandles(ctx, map[string]*domain.Candle{
		ticker: {Timestamp: ts, Open: 80000, High: 81000, Low: 79000, Close: 80500, Volume: 1000},
	}, domain.IntervalMinute); err != nil {
		t.Fatalf("1차 INSERT 실패: %v", err)
	}

	// 2차 INSERT (같은 candle_time, 새로운 값)
	if err := repo.BulkInsertCandles(ctx, map[string]*domain.Candle{
		ticker: {Timestamp: ts, Open: 80000, High: 82000, Low: 78500, Close: 81500, Volume: 2500},
	}, domain.IntervalMinute); err != nil {
		t.Fatalf("2차 UPDATE 실패: %v", err)
	}

	var highP, closeP, volume int64
	_ = db.QueryRowContext(ctx,
		"SELECT high_price, close_price, volume FROM candle_1m WHERE ticker=? AND candle_time=?",
		ticker, ts,
	).Scan(&highP, &closeP, &volume)

	if highP != 82000 {
		t.Errorf("high_price: want 82000 (업데이트됨), got %d", highP)
	}
	if closeP != 81500 {
		t.Errorf("close_price: want 81500 (업데이트됨), got %d", closeP)
	}
	if volume != 2500 {
		t.Errorf("volume: want 2500 (업데이트됨), got %d", volume)
	}
}

// ─── BulkInsertCandlesSlice (과거 일봉 → candle_1d) 통합 테스트 ──────────────

// TestBulkInsertCandlesSlice_MultipleCandles_InsertsAll 여러 날짜의 일봉을 한 번에 삽입한다.
func TestBulkInsertCandlesSlice_MultipleCandles_InsertsAll(t *testing.T) {
	repo, db, teardown := newTestRepoWithDB(t)
	defer teardown()

	ticker := "ZSLC01"
	insertTestStockMeta(t, db, []string{ticker})
	defer cleanupTestData(t, db, []string{ticker})

	// candle_date: DATE 형식 (MySQL은 YYYYMMDD도 허용하나 YYYY-MM-DD 권장)
	candles := []domain.Candle{
		{Timestamp: "20240101", Open: 70000, High: 71000, Low: 69000, Close: 70500, Volume: 1000000},
		{Timestamp: "20240102", Open: 70500, High: 72000, Low: 70000, Close: 71500, Volume: 1200000},
		{Timestamp: "20240103", Open: 71500, High: 73000, Low: 71000, Close: 72000, Volume: 900000},
	}

	ctx := context.Background()
	if err := repo.BulkInsertCandlesSlice(ctx, candles, ticker, domain.IntervalDay); err != nil {
		t.Fatalf("BulkInsertCandlesSlice 실패: %v", err)
	}

	var count int
	_ = db.QueryRowContext(ctx, "SELECT COUNT(*) FROM candle_1d WHERE ticker=?", ticker).Scan(&count)
	if count != 3 {
		t.Errorf("3개의 일봉이 삽입되어야 한다, got %d", count)
	}
}

// TestBulkInsertCandlesSlice_EmptySlice_IsNoOp 빈 슬라이스는 에러 없이 처리된다.
func TestBulkInsertCandlesSlice_EmptySlice_IsNoOp(t *testing.T) {
	repo, _, teardown := newTestRepoWithDB(t)
	defer teardown()

	if err := repo.BulkInsertCandlesSlice(context.Background(), []domain.Candle{}, "ZSLC99", domain.IntervalDay); err != nil {
		t.Errorf("빈 슬라이스에서 에러 반환: %v", err)
	}
}

// TestBulkInsertCandlesSlice_DuplicateDate_UpdatesExisting 같은 날짜 재삽입 시 값이 갱신된다.
func TestBulkInsertCandlesSlice_DuplicateDate_UpdatesExisting(t *testing.T) {
	repo, db, teardown := newTestRepoWithDB(t)
	defer teardown()

	ticker := "ZDUP1D"
	insertTestStockMeta(t, db, []string{ticker})
	defer cleanupTestData(t, db, []string{ticker})

	ctx := context.Background()
	date := "20240115"

	original := []domain.Candle{
		{Timestamp: date, Open: 70000, High: 71000, Low: 69000, Close: 70500, Volume: 1000000},
	}
	if err := repo.BulkInsertCandlesSlice(ctx, original, ticker, domain.IntervalDay); err != nil {
		t.Fatalf("초기 삽입 실패: %v", err)
	}

	// KIS Backfill 재동기화 시나리오: 같은 날짜에 더 정확한 데이터로 갱신
	updated := []domain.Candle{
		{Timestamp: date, Open: 70000, High: 73000, Low: 68000, Close: 71500, Volume: 2000000},
	}
	if err := repo.BulkInsertCandlesSlice(ctx, updated, ticker, domain.IntervalDay); err != nil {
		t.Fatalf("재삽입(업데이트) 실패: %v", err)
	}

	var highP, volume int64
	_ = db.QueryRowContext(ctx,
		"SELECT high_price, volume FROM candle_1d WHERE ticker=? AND candle_date=?",
		ticker, date,
	).Scan(&highP, &volume)

	if highP != 73000 {
		t.Errorf("high_price: want 73000 (업데이트됨), got %d", highP)
	}
	if volume != 2000000 {
		t.Errorf("volume: want 2000000 (업데이트됨), got %d", volume)
	}
}

// ─── GetCandlesFromDB 통합 테스트 ─────────────────────────────────────────────

// TestGetCandlesFromDB_1m_ReturnsDescendingOrder INSERT 후 DESC 정렬로 조회된다.
func TestGetCandlesFromDB_1m_ReturnsDescendingOrder(t *testing.T) {
	repo, db, teardown := newTestRepoWithDB(t)
	defer teardown()

	ticker := "ZORD1M"
	insertTestStockMeta(t, db, []string{ticker})
	defer cleanupTestData(t, db, []string{ticker})

	ctx := context.Background()
	candles := []domain.Candle{
		{Timestamp: "2024-01-01 09:01:00", Open: 80000, High: 80500, Low: 79500, Close: 80200, Volume: 100},
		{Timestamp: "2024-01-01 09:02:00", Open: 80200, High: 81000, Low: 80100, Close: 80800, Volume: 200},
		{Timestamp: "2024-01-01 09:03:00", Open: 80800, High: 81500, Low: 80500, Close: 81200, Volume: 150},
	}
	if err := repo.BulkInsertCandlesSlice(ctx, candles, ticker, domain.IntervalMinute); err != nil {
		t.Fatalf("INSERT 실패: %v", err)
	}

	result, err := repo.GetCandlesFromDB(ctx, ticker, domain.IntervalMinute, 10, "")
	if err != nil {
		t.Fatalf("GetCandlesFromDB 실패: %v", err)
	}
	if len(result) != 3 {
		t.Fatalf("3개 캔들 기대, got %d", len(result))
	}

	// DESC 정렬: 가장 최신(09:03)이 첫 번째
	if result[0].Timestamp != "2024-01-01 09:03:00" {
		t.Errorf("첫 번째 캔들(최신): want '2024-01-01 09:03:00', got '%s'", result[0].Timestamp)
	}
	if result[2].Timestamp != "2024-01-01 09:01:00" {
		t.Errorf("마지막 캔들(가장 오래됨): want '2024-01-01 09:01:00', got '%s'", result[2].Timestamp)
	}
}

// TestGetCandlesFromDB_1d_ReturnsDescendingOrder 일봉 DESC 정렬 검증
func TestGetCandlesFromDB_1d_ReturnsDescendingOrder(t *testing.T) {
	repo, db, teardown := newTestRepoWithDB(t)
	defer teardown()

	ticker := "ZORD1D"
	insertTestStockMeta(t, db, []string{ticker})
	defer cleanupTestData(t, db, []string{ticker})

	ctx := context.Background()
	candles := []domain.Candle{
		{Timestamp: "20240101", Open: 70000, High: 71000, Low: 69000, Close: 70500, Volume: 1000000},
		{Timestamp: "20240102", Open: 70500, High: 72000, Low: 70000, Close: 71500, Volume: 1200000},
		{Timestamp: "20240103", Open: 71500, High: 73000, Low: 71000, Close: 72000, Volume: 900000},
	}
	if err := repo.BulkInsertCandlesSlice(ctx, candles, ticker, domain.IntervalDay); err != nil {
		t.Fatalf("INSERT 실패: %v", err)
	}

	result, err := repo.GetCandlesFromDB(ctx, ticker, domain.IntervalDay, 10, "")
	if err != nil {
		t.Fatalf("GetCandlesFromDB 실패: %v", err)
	}
	if len(result) != 3 {
		t.Fatalf("3개 캔들 기대, got %d", len(result))
	}

	// DESC 정렬: 20240103이 첫 번째
	// MySQL DATE → "2024-01-03" 형식으로 반환됨
	if result[0].Timestamp != "2024-01-03" {
		t.Errorf("첫 번째 캔들(최신): want '2024-01-03', got '%s'", result[0].Timestamp)
	}
	if result[2].Timestamp != "2024-01-01" {
		t.Errorf("마지막 캔들(가장 오래됨): want '2024-01-01', got '%s'", result[2].Timestamp)
	}
}

// TestGetCandlesFromDB_LimitRespected limit 파라미터가 적용된다.
func TestGetCandlesFromDB_LimitRespected(t *testing.T) {
	repo, db, teardown := newTestRepoWithDB(t)
	defer teardown()

	ticker := "ZLMT01"
	insertTestStockMeta(t, db, []string{ticker})
	defer cleanupTestData(t, db, []string{ticker})

	ctx := context.Background()
	candles := []domain.Candle{
		{Timestamp: "2024-01-01 10:01:00", Open: 80000, High: 80500, Low: 79500, Close: 80200, Volume: 100},
		{Timestamp: "2024-01-01 10:02:00", Open: 80200, High: 81000, Low: 80100, Close: 80800, Volume: 200},
		{Timestamp: "2024-01-01 10:03:00", Open: 80800, High: 81500, Low: 80500, Close: 81200, Volume: 150},
		{Timestamp: "2024-01-01 10:04:00", Open: 81200, High: 82000, Low: 81000, Close: 81800, Volume: 300},
		{Timestamp: "2024-01-01 10:05:00", Open: 81800, High: 82500, Low: 81500, Close: 82200, Volume: 250},
	}
	if err := repo.BulkInsertCandlesSlice(ctx, candles, ticker, domain.IntervalMinute); err != nil {
		t.Fatalf("INSERT 실패: %v", err)
	}

	result, err := repo.GetCandlesFromDB(ctx, ticker, domain.IntervalMinute, 3, "")
	if err != nil {
		t.Fatalf("GetCandlesFromDB 실패: %v", err)
	}
	if len(result) != 3 {
		t.Errorf("limit=3 적용: want 3, got %d", len(result))
	}
}

// TestGetCandlesFromDB_NotFound_ReturnsEmpty 없는 종목은 빈 슬라이스를 반환한다.
func TestGetCandlesFromDB_NotFound_ReturnsEmpty(t *testing.T) {
	repo, _, teardown := newTestRepoWithDB(t)
	defer teardown()

	result, err := repo.GetCandlesFromDB(context.Background(), "ZZZNONE", domain.IntervalMinute, 10, "")
	if err != nil {
		t.Fatalf("없는 종목 조회에서 에러: %v", err)
	}
	if len(result) != 0 {
		t.Errorf("없는 종목은 빈 슬라이스여야 한다, got %d items", len(result))
	}
}

// TestGetCandlesFromDB_AllFieldsCorrect OHLCV 모든 필드가 정확히 조회된다.
func TestGetCandlesFromDB_AllFieldsCorrect(t *testing.T) {
	repo, db, teardown := newTestRepoWithDB(t)
	defer teardown()

	ticker := "ZFLD01"
	insertTestStockMeta(t, db, []string{ticker})
	defer cleanupTestData(t, db, []string{ticker})

	ctx := context.Background()
	want := domain.Candle{
		Timestamp: "2024-03-15 14:30:00",
		Open:      72000,
		High:      73500,
		Low:       71000,
		Close:     73000,
		Volume:    2500000,
	}

	if err := repo.BulkInsertCandlesSlice(ctx, []domain.Candle{want}, ticker, domain.IntervalMinute); err != nil {
		t.Fatalf("INSERT 실패: %v", err)
	}

	result, err := repo.GetCandlesFromDB(ctx, ticker, domain.IntervalMinute, 10, "")
	if err != nil {
		t.Fatalf("GetCandlesFromDB 실패: %v", err)
	}
	if len(result) != 1 {
		t.Fatalf("1개 캔들 기대, got %d", len(result))
	}

	got := result[0]
	if got.Open != want.Open || got.High != want.High || got.Low != want.Low ||
		got.Close != want.Close || got.Volume != want.Volume {
		t.Errorf("OHLCV 불일치:\n want: %+v\n  got: %+v", want, got)
	}
	if got.Timestamp != want.Timestamp {
		t.Errorf("Timestamp: want '%s', got '%s'", want.Timestamp, got.Timestamp)
	}
}
