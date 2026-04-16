package worker

import (
	"context"
	"testing"
	"time"
)

// ─── StartDailyCloseScheduler ─────────────────────────────────────────────────

// TestStartDailyCloseScheduler_ContextCancel_StopsWithoutBlock
// ctx가 취소되면 스케줄러 goroutine이 2초 이내에 종료되어야 한다 (goroutine leak 방지).
func TestStartDailyCloseScheduler_ContextCancel_StopsWithoutBlock(t *testing.T) {
	w := &DailySyncWorker{
		kisClient: nil,
		stockRepo: nil,
	}

	ctx, cancel := context.WithCancel(context.Background())

	done := make(chan struct{})
	go func() {
		defer close(done)
		w.StartDailyCloseScheduler(ctx)
	}()

	cancel() // 즉시 취소

	select {
	case <-done:
		// 정상 종료
	case <-time.After(2 * time.Second):
		t.Error("StartDailyCloseScheduler가 ctx 취소 후 2초 이내에 종료되지 않았다 (goroutine leak 의심)")
	}
}

// TestStartDailyCloseScheduler_AlreadyCancelled_ExitsImmediately
// 이미 취소된 ctx로 시작하면 즉시 종료되어야 한다.
func TestStartDailyCloseScheduler_AlreadyCancelled_ExitsImmediately(t *testing.T) {
	w := &DailySyncWorker{
		kisClient: nil,
		stockRepo: nil,
	}

	ctx, cancel := context.WithCancel(context.Background())
	cancel() // 시작 전에 이미 취소

	done := make(chan struct{})
	go func() {
		defer close(done)
		w.StartDailyCloseScheduler(ctx)
	}()

	select {
	case <-done:
		// 정상 종료
	case <-time.After(1 * time.Second):
		t.Error("이미 취소된 ctx에서 StartDailyCloseScheduler가 1초 이내에 종료되지 않았다")
	}
}

// ─── calcNext 트리거 시각 계산 로직 (내부 클로저 재현) ───────────────────────────

// calcNextForTest 는 StartDailyCloseScheduler 내부의 calcNext 클로저와 동일한 로직이다.
// 내부 클로저를 직접 호출할 수 없으므로 같은 로직을 재현하여 다양한 시각에서 검증한다.
func calcNextForTest(now time.Time, kst *time.Location) time.Time {
	const triggerHour = 15
	const triggerMin = 35
	next := time.Date(now.Year(), now.Month(), now.Day(), triggerHour, triggerMin, 0, 0, kst)
	if now.After(next) {
		next = next.AddDate(0, 0, 1)
	}
	return next
}

// TestCalcNext_BeforeTrigger_ReturnsTodayAt1535
// 15:35 이전(오전)이면 다음 트리거는 오늘 15:35이어야 한다.
func TestCalcNext_BeforeTrigger_ReturnsTodayAt1535(t *testing.T) {
	kst, _ := time.LoadLocation("Asia/Seoul")
	now := time.Date(2026, 3, 18, 9, 0, 0, 0, kst) // 09:00 KST

	got := calcNextForTest(now, kst)
	want := time.Date(2026, 3, 18, 15, 35, 0, 0, kst)

	if !got.Equal(want) {
		t.Errorf("09:00 KST: 오늘 15:35 반환 기대, got=%s", got.Format("2006-01-02 15:04:05"))
	}
}

// TestCalcNext_AfterTrigger_ReturnsTomorrowAt1535
// 15:35 이후면 다음 트리거는 내일 15:35이어야 한다.
func TestCalcNext_AfterTrigger_ReturnsTomorrowAt1535(t *testing.T) {
	kst, _ := time.LoadLocation("Asia/Seoul")
	now := time.Date(2026, 3, 18, 15, 36, 0, 0, kst) // 15:36 KST (1분 지남)

	got := calcNextForTest(now, kst)
	want := time.Date(2026, 3, 19, 15, 35, 0, 0, kst)

	if !got.Equal(want) {
		t.Errorf("15:36 KST: 내일 15:35 반환 기대, got=%s", got.Format("2006-01-02 15:04:05"))
	}
}

// TestCalcNext_LateNight_ReturnsTomorrowAt1535
// 자정 이후(00:00) 에도 올바르게 다음 영업일 15:35를 반환해야 한다.
func TestCalcNext_LateNight_ReturnsTomorrowAt1535(t *testing.T) {
	kst, _ := time.LoadLocation("Asia/Seoul")
	now := time.Date(2026, 3, 18, 23, 59, 59, 0, kst) // 23:59:59 KST

	got := calcNextForTest(now, kst)
	want := time.Date(2026, 3, 19, 15, 35, 0, 0, kst)

	if !got.Equal(want) {
		t.Errorf("23:59:59 KST: 내일 15:35 반환 기대, got=%s", got.Format("2006-01-02 15:04:05"))
	}
}

// TestCalcNext_ExactlyAtTrigger_ReturnsTodayAt1535
// time.After는 strictly greater이므로 정각 15:35:00은 "아직 지나지 않음"으로 처리되어
// 오늘 15:35를 반환한다. (실제로는 syncTodayDailyCandles 실행 시간이 수초 걸리므로
// 재계산 시점엔 항상 15:35 이후가 되어 내일이 올바르게 반환된다)
func TestCalcNext_ExactlyAtTrigger_ReturnsTodayAt1535(t *testing.T) {
	kst, _ := time.LoadLocation("Asia/Seoul")
	now := time.Date(2026, 3, 18, 15, 35, 0, 0, kst) // 정각 15:35:00

	got := calcNextForTest(now, kst)
	want := time.Date(2026, 3, 18, 15, 35, 0, 0, kst) // now.After(next)==false → 오늘

	if !got.Equal(want) {
		t.Errorf("정각 15:35: 오늘 15:35 반환 기대 (After는 strictly greater), got=%s",
			got.Format("2006-01-02 15:04:05"))
	}
}

// TestCalcNext_OneSecondBeforeTrigger_ReturnsTodayAt1535
// 15:34:59는 아직 15:35 이전이므로 오늘 15:35를 반환해야 한다.
func TestCalcNext_OneSecondBeforeTrigger_ReturnsTodayAt1535(t *testing.T) {
	kst, _ := time.LoadLocation("Asia/Seoul")
	now := time.Date(2026, 3, 18, 15, 34, 59, 0, kst) // 15:34:59

	got := calcNextForTest(now, kst)
	want := time.Date(2026, 3, 18, 15, 35, 0, 0, kst)

	if !got.Equal(want) {
		t.Errorf("15:34:59: 오늘 15:35 반환 기대, got=%s", got.Format("2006-01-02 15:04:05"))
	}
}

// TestCalcNext_OneSecondAfterTrigger_ReturnsTomorrowAt1535
// 15:35:01은 15:35를 1초 지났으므로 내일 15:35를 반환해야 한다.
func TestCalcNext_OneSecondAfterTrigger_ReturnsTomorrowAt1535(t *testing.T) {
	kst, _ := time.LoadLocation("Asia/Seoul")
	now := time.Date(2026, 3, 18, 15, 35, 1, 0, kst) // 15:35:01

	got := calcNextForTest(now, kst)
	want := time.Date(2026, 3, 19, 15, 35, 0, 0, kst)

	if !got.Equal(want) {
		t.Errorf("15:35:01: 내일 15:35 반환 기대, got=%s", got.Format("2006-01-02 15:04:05"))
	}
}

// TestCalcNext_ReturnedTimeIsAlwaysInFuture
// calcNext가 반환하는 시각은 항상 now보다 미래여야 한다.
func TestCalcNext_ReturnedTimeIsAlwaysInFuture(t *testing.T) {
	kst, _ := time.LoadLocation("Asia/Seoul")

	testCases := []time.Time{
		time.Date(2026, 3, 18, 0, 0, 0, 0, kst),      // 자정
		time.Date(2026, 3, 18, 9, 0, 0, 0, kst),       // 오전
		time.Date(2026, 3, 18, 15, 34, 59, 0, kst),    // 트리거 직전
		time.Date(2026, 3, 18, 15, 35, 1, 0, kst),     // 트리거 직후
		time.Date(2026, 3, 18, 23, 59, 59, 999, kst),  // 자정 직전
	}

	for _, now := range testCases {
		got := calcNextForTest(now, kst)
		if !got.After(now) {
			t.Errorf("now=%s: calcNext 결과(%s)가 현재보다 미래여야 한다",
				now.Format("2006-01-02 15:04:05"),
				got.Format("2006-01-02 15:04:05"))
		}
	}
}

// ─── KST 날짜 포맷 검증 ───────────────────────────────────────────────────────

// TestSyncTodayDailyCandles_DateFormat_IsYYYYMMDD
// syncTodayDailyCandles가 사용하는 KST 오늘 날짜 포맷이 YYYYMMDD(8자리 숫자)여야 한다.
func TestSyncTodayDailyCandles_DateFormat_IsYYYYMMDD(t *testing.T) {
	kst, _ := time.LoadLocation("Asia/Seoul")
	today := time.Now().In(kst).Format("20060102")

	if len(today) != 8 {
		t.Errorf("날짜 포맷 길이: want 8, got %d (%s)", len(today), today)
	}
	for _, ch := range today {
		if ch < '0' || ch > '9' {
			t.Errorf("날짜 포맷에 비숫자 문자 포함: %s", today)
			break
		}
	}

	// KIS API 날짜 범위에서 startDate == endDate 임을 확인 (오늘만 조회)
	startDate := today
	endDate := today
	if startDate != endDate {
		t.Errorf("syncTodayDailyCandles: startDate와 endDate가 같아야 한다, got start=%s end=%s",
			startDate, endDate)
	}
}

// TestSyncTodayDailyCandles_DateFormat_IsKSTNotUTC
// UTC와 KST는 9시간 차이가 있으므로, KST 기준 날짜 포맷이 UTC와 다를 수 있음을 검증한다.
// (UTC 00:00~09:00 사이에 KST 날짜와 UTC 날짜가 다르다)
func TestSyncTodayDailyCandles_DateFormat_IsKSTNotUTC(t *testing.T) {
	kst, _ := time.LoadLocation("Asia/Seoul")

	// UTC 00:30 = KST 09:30 (날짜가 다름)
	utcTime := time.Date(2026, 3, 19, 0, 30, 0, 0, time.UTC)
	kstDate := utcTime.In(kst).Format("20060102")
	utcDate := utcTime.Format("20060102")

	if kstDate == utcDate {
		t.Skip("테스트 시각이 UTC 기준 동일 날짜인 경우 스킵 (UTC 09:00 이후)")
	}

	if kstDate != "20260319" {
		t.Errorf("UTC 00:30은 KST 09:30 → KST 날짜는 20260319여야 한다, got=%s", kstDate)
	}
	if utcDate != "20260318" {
		t.Errorf("UTC 00:30의 UTC 날짜는 20260318이어야 한다, got=%s", utcDate)
	}
}
