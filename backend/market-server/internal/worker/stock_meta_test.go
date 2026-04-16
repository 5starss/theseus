package worker

import (
	"regexp"
	"testing"
)

// ─── TargetStocks Map ─────────────────────────────────────────────────────────

// TestTargetStocks_Has100Entries 구독 대상 종목이 정확히 100개이다.
func TestTargetStocks_Has100Entries(t *testing.T) {
	if len(TargetStocks) != 100 {
		t.Errorf("TargetStocks 종목 수: got %d, want 100", len(TargetStocks))
	}
}

// TestTargetStocks_AllTickersAreValid 모든 티커가 6자리 숫자 코드이다.
func TestTargetStocks_AllTickersAreValid(t *testing.T) {
	tickerRe := regexp.MustCompile(`^\d{6}$`)
	for ticker := range TargetStocks {
		if !tickerRe.MatchString(ticker) {
			t.Errorf("유효하지 않은 티커 코드: %q (6자리 숫자여야 함)", ticker)
		}
	}
}

// TestTargetStocks_AllNamesAreNonEmpty 모든 종목명이 비어 있지 않다.
func TestTargetStocks_AllNamesAreNonEmpty(t *testing.T) {
	for ticker, name := range TargetStocks {
		if name == "" {
			t.Errorf("종목명이 비어 있음: ticker=%q", ticker)
		}
	}
}

// TestTargetStocks_FiveSessionsCapacity 100종목은 세션당 20종목 제한 하에 정확히 5세션으로 처리 가능하다.
func TestTargetStocks_FiveSessionsCapacity(t *testing.T) {
	const maxPerSession = 20
	totalStocks := len(TargetStocks)

	sessionsNeeded := (totalStocks + maxPerSession - 1) / maxPerSession // ceil 나눗셈
	if sessionsNeeded != 5 {
		t.Errorf("100종목 / 20종목 = 5세션이어야 함, got %d세션 (총 %d종목)", sessionsNeeded, totalStocks)
	}
}

// TestTargetStocks_EvenlyDivisibleBySession 100종목이 20으로 나누어 떨어진다.
func TestTargetStocks_EvenlyDivisibleBySession(t *testing.T) {
	const maxPerSession = 20
	if len(TargetStocks)%maxPerSession != 0 {
		t.Errorf("TargetStocks(%d)이 세션당 %d종목으로 균등 분배되지 않음 (나머지: %d)",
			len(TargetStocks), maxPerSession, len(TargetStocks)%maxPerSession)
	}
}

// TestTargetStocks_KnownTickersPresent 필수 대형주 티커가 포함되어 있다.
func TestTargetStocks_KnownTickersPresent(t *testing.T) {
	mustHave := map[string]string{
		"005930": "삼성전자",
		"000660": "SK하이닉스",
		"005380": "현대차",
	}
	for ticker, wantName := range mustHave {
		gotName, ok := TargetStocks[ticker]
		if !ok {
			t.Errorf("필수 종목 미포함: ticker=%q (%s)", ticker, wantName)
			continue
		}
		if gotName != wantName {
			t.Errorf("종목명 불일치: ticker=%q got=%q, want=%q", ticker, gotName, wantName)
		}
	}
}

// ─── GetTargetTickers ────────────────────────────────────────────────────────

// TestGetTargetTickers_Length100 반환 리스트가 100개다.
func TestGetTargetTickers_Length100(t *testing.T) {
	tickers := GetTargetTickers()
	if len(tickers) != 100 {
		t.Errorf("GetTargetTickers() 길이: got %d, want 100", len(tickers))
	}
}

// TestGetTargetTickers_AllInTargetStocks 반환된 모든 티커가 TargetStocks에 존재한다.
func TestGetTargetTickers_AllInTargetStocks(t *testing.T) {
	tickers := GetTargetTickers()
	for _, ticker := range tickers {
		if _, ok := TargetStocks[ticker]; !ok {
			t.Errorf("GetTargetTickers()가 TargetStocks에 없는 티커 반환: %q", ticker)
		}
	}
}

// TestGetTargetTickers_NoNilOrEmpty 반환 리스트에 빈 문자열이 없다.
func TestGetTargetTickers_NoNilOrEmpty(t *testing.T) {
	for _, ticker := range GetTargetTickers() {
		if ticker == "" {
			t.Error("GetTargetTickers()에 빈 문자열 티커가 포함됨")
		}
	}
}

// TestGetTargetTickers_UniqueElements 반환된 티커에 중복이 없다.
func TestGetTargetTickers_UniqueElements(t *testing.T) {
	seen := make(map[string]bool)
	for _, ticker := range GetTargetTickers() {
		if seen[ticker] {
			t.Errorf("중복 티커 발견: %q", ticker)
		}
		seen[ticker] = true
	}
}

// TestGetTargetTickers_MatchesMapKeys 반환 티커 집합이 TargetStocks의 키 집합과 완전히 일치한다.
func TestGetTargetTickers_MatchesMapKeys(t *testing.T) {
	tickers := GetTargetTickers()
	tickerSet := make(map[string]bool, len(tickers))
	for _, tk := range tickers {
		tickerSet[tk] = true
	}

	for mapKey := range TargetStocks {
		if !tickerSet[mapKey] {
			t.Errorf("TargetStocks의 키 %q가 GetTargetTickers() 결과에 없음", mapKey)
		}
	}
}

// ─── 하위호환 별칭 ─────────────────────────────────────────────────────────────

// TestTop40Stocks_IsAliasForTargetStocks Top40Stocks가 TargetStocks와 동일한 맵이다.
func TestTop40Stocks_IsAliasForTargetStocks(t *testing.T) {
	if len(Top40Stocks) != len(TargetStocks) {
		t.Errorf("Top40Stocks 크기(%d) ≠ TargetStocks 크기(%d)", len(Top40Stocks), len(TargetStocks))
	}
	for ticker, name := range TargetStocks {
		if Top40Stocks[ticker] != name {
			t.Errorf("Top40Stocks[%q] = %q, TargetStocks[%q] = %q — 불일치",
				ticker, Top40Stocks[ticker], ticker, name)
		}
	}
}

// TestGetTop40Tickers_SameResultAsGetTargetTickers 두 함수의 반환 결과가 동일한 집합이다.
func TestGetTop40Tickers_SameResultAsGetTargetTickers(t *testing.T) {
	top40 := GetTop40Tickers()
	target := GetTargetTickers()

	if len(top40) != len(target) {
		t.Fatalf("GetTop40Tickers() 길이(%d) ≠ GetTargetTickers() 길이(%d)", len(top40), len(target))
	}

	// 집합 비교
	targetSet := make(map[string]bool, len(target))
	for _, tk := range target {
		targetSet[tk] = true
	}
	for _, tk := range top40 {
		if !targetSet[tk] {
			t.Errorf("GetTop40Tickers()에만 있는 티커: %q", tk)
		}
	}
}

// TestGetTop40Tickers_LengthIsHundred 레거시 함수도 100종목을 반환한다 (이름과 달리).
func TestGetTop40Tickers_LengthIsHundred(t *testing.T) {
	if len(GetTop40Tickers()) != 100 {
		t.Errorf("GetTop40Tickers() 길이: got %d, want 100 (TargetStocks 전체 위임)", len(GetTop40Tickers()))
	}
}

// ─── 순서 보장 (버그 수정 핵심 검증) ──────────────────────────────────────────

// TestGetTargetTickers_OrderMatchesSlice GetTargetTickers()의 순서가 TargetStocksList와 완전히 일치한다.
// map을 순회하던 기존 구현은 매번 무작위 순서를 반환했으므로, 슬라이스 기반으로 수정 후 이를 검증한다.
func TestGetTargetTickers_OrderMatchesSlice(t *testing.T) {
	tickers := GetTargetTickers()
	for i, s := range TargetStocksList {
		if tickers[i] != s.Ticker {
			t.Errorf("index %d: got %q, want %q — TargetStocksList 순서와 불일치", i, tickers[i], s.Ticker)
		}
	}
}

// TestGetTargetTickers_Deterministic 동일한 결과를 항상 반환한다 (결정론적).
func TestGetTargetTickers_Deterministic(t *testing.T) {
	first := GetTargetTickers()
	for round := 0; round < 10; round++ {
		got := GetTargetTickers()
		for i := range first {
			if got[i] != first[i] {
				t.Errorf("round %d, index %d: got %q, want %q — 순서가 달라짐", round, i, got[i], first[i])
			}
		}
	}
}

// TestGetTargetTickers_SessionBoundaries 세션 경계 종목(0번, 19번, 20번, 39번 ...)이 정확하다.
// KIS 웹소켓은 세션당 20종목 제한이므로 세션 경계가 정확해야 한다.
func TestGetTargetTickers_SessionBoundaries(t *testing.T) {
	const sessionSize = 20
	tickers := GetTargetTickers()

	tests := []struct {
		idx        int
		wantTicker string
		label      string
	}{
		{0, TargetStocksList[0].Ticker, "세션1 첫 종목"},
		{sessionSize - 1, TargetStocksList[sessionSize-1].Ticker, "세션1 마지막 종목"},
		{sessionSize, TargetStocksList[sessionSize].Ticker, "세션2 첫 종목"},
		{sessionSize*2 - 1, TargetStocksList[sessionSize*2-1].Ticker, "세션2 마지막 종목"},
		{sessionSize * 2, TargetStocksList[sessionSize*2].Ticker, "세션3 첫 종목"},
	}

	for _, tc := range tests {
		if tickers[tc.idx] != tc.wantTicker {
			t.Errorf("%s (index %d): got %q, want %q", tc.label, tc.idx, tickers[tc.idx], tc.wantTicker)
		}
	}
}

// TestTargetStocksList_NoDuplicateTickers TargetStocksList에 중복 티커가 없다.
func TestTargetStocksList_NoDuplicateTickers(t *testing.T) {
	seen := make(map[string]int)
	for i, s := range TargetStocksList {
		if prev, ok := seen[s.Ticker]; ok {
			t.Errorf("중복 티커 %q: index %d와 %d에서 중복", s.Ticker, prev, i)
		}
		seen[s.Ticker] = i
	}
}

// TestTargetStocksList_SessionGroups 각 세션(20종목 단위)이 TargetStocksList에 정확히 정의되어 있다.
func TestTargetStocksList_SessionGroups(t *testing.T) {
	const sessionSize = 20
	totalSessions := len(TargetStocksList) / sessionSize

	for session := 0; session < totalSessions; session++ {
		start := session * sessionSize
		end := start + sessionSize
		group := TargetStocksList[start:end]
		if len(group) != sessionSize {
			t.Errorf("세션 %d: 종목 수 %d (want %d)", session+1, len(group), sessionSize)
		}
	}
}
