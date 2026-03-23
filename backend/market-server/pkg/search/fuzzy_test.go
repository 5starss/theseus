package search

import (
	"testing"
)

// ─── Normalize 테스트 ────────────────────────────────────────────────────────

func TestNormalize(t *testing.T) {
	tests := []struct {
		input string
		want  string
	}{
		{"삼성 전자", "삼성전자"},
		{"KODEX 200", "kodex200"},
		{"  공백  앞뒤  ", "공백앞뒤"},
		{"", ""},
		{"NoSpaces", "nospaces"},
		{"TIGER200", "tiger200"},
		{"한글ENGLISH혼합", "한글english혼합"},
	}
	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			got := Normalize(tt.input)
			if got != tt.want {
				t.Errorf("Normalize(%q) = %q, want %q", tt.input, got, tt.want)
			}
		})
	}
}

// ─── levenshtein 테스트 ───────────────────────────────────────────────────────

func TestLevenshtein(t *testing.T) {
	tests := []struct {
		a, b string
		want int
	}{
		{"", "", 0},
		{"abc", "abc", 0},
		{"abc", "axc", 1},    // 치환 1
		{"abc", "ab", 1},     // 삭제 1
		{"ab", "abc", 1},     // 삽입 1
		{"abc", "", 3},       // 전체 삭제
		{"", "abc", 3},       // 전체 삽입
		{"삼성", "삼성전자", 2}, // 한글 삽입 2
		{"현대오투", "현대오토", 1},// 한글 치환 1
	}
	for _, tt := range tests {
		t.Run(tt.a+"→"+tt.b, func(t *testing.T) {
			got := levenshtein([]rune(tt.a), []rune(tt.b))
			if got != tt.want {
				t.Errorf("levenshtein(%q, %q) = %d, want %d", tt.a, tt.b, got, tt.want)
			}
		})
	}
}

func TestEvaluateMatch(t *testing.T) {
	tests := []struct {
		desc         string
		query        string
		targetName   string
		targetTicker string
		wantRank     MatchScoreType
	}{
		{
			desc:         "Exact Name Substring - KODEX 200",
			query:        "200",
			targetName:   "KODEX 200",
			targetTicker: "069500",
			wantRank:     RankExactName,
		},
		{
			desc:         "Exact Ticker Substring",
			query:        "005",
			targetName:   "삼성전자",
			targetTicker: "005930",
			wantRank:     RankExactTicker,
		},
		{
			desc:         "Fuzzy match 1 error (현대오투 -> 현대오토에버)",
			query:        "현대오투",
			targetName:   "현대오토에버",
			targetTicker: "307950",
			wantRank:     RankFuzzyName,
		},
		{
			desc:         "No Match (too many errors)",
			query:        "가나다라마",
			targetName:   "현대오토에버",
			targetTicker: "307950",
			wantRank:     RankNone,
		},
		{
			desc:         "Fuzzy match 2 errors (헌대오투 -> 현대오토에버)", // 4 length -> max 1 error. 
			query:        "헌대오투",
			targetName:   "현대오토에버",
			targetTicker: "307950",
			wantRank:     RankNone, // len(query)=4 => maxErrors=1, so distance=2 => fail
		},
		{
			desc:         "Fuzzy match 2 errors long enough (오투에버주 -> 현대오토에버)", 
			query:        "오투에벌", // len=4, maxErrors=1
			targetName:   "현대오토에버",
			targetTicker: "307950",
			wantRank:     RankNone,
		},
		{
			desc:         "Fuzzy match 2 errors really long (헌대오투에버 -> 현대오토에버)", 
			query:        "헌대오투에버", // len=6 => max 2 errors
			targetName:   "현대오토에버",
			targetTicker: "307950",
			wantRank:     RankFuzzyName,
		},
		{
			desc:         "Number matches Name over Ticker (TIGER 200 vs 005200)", 
			query:        "200", 
			targetName:   "TIGER 200",
			targetTicker: "122900",
			wantRank:     RankExactName, // 이름에 200이 있으므로 0순위
		},
	}

	for _, tt := range tests {
		t.Run(tt.desc, func(t *testing.T) {
			got := EvaluateMatch(Normalize(tt.query), tt.targetName, tt.targetTicker, 0)
			if got.Rank != tt.wantRank {
				t.Errorf("EvaluateMatch() Rank = %v, want %v", got.Rank, tt.wantRank)
			}
		})
	}
}

// TestEvaluateMatch_AdditionalCases 엣지케이스 및 경계값 추가 테스트
func TestEvaluateMatch_AdditionalCases(t *testing.T) {
	tests := []struct {
		desc         string
		query        string // Normalize된 상태로 전달
		targetName   string
		targetTicker string
		wantRank     MatchScoreType
	}{
		{
			desc:         "1글자 검색어 - 이름 일치",
			query:        "삼",
			targetName:   "삼성전자",
			targetTicker: "005930",
			wantRank:     RankExactName,
		},
		{
			desc:         "1글자 검색어 - 퍼지 미허용, 이름 불일치",
			query:        "영",
			targetName:   "삼성전자",
			targetTicker: "005930",
			wantRank:     RankNone,
		},
		{
			desc:         "2글자 검색어 - 퍼지 미허용(maxErrors=0), RankNone",
			query:        "삼셩", // "삼성"의 오타 1개 → maxErrors=0 이므로 불일치
			targetName:   "삼성전자",
			targetTicker: "005930",
			wantRank:     RankNone,
		},
		{
			desc:         "공백 포함 종목명 - 공백 제거 후 이름 일치",
			query:        "kodex200", // 공백 제거된 쿼리
			targetName:   "KODEX 200",
			targetTicker: "069500",
			wantRank:     RankExactName,
		},
		{
			desc:         "대소문자 무관 - 소문자 쿼리로 대문자 이름 매칭",
			query:        "tiger",
			targetName:   "TIGER 200",
			targetTicker: "122900",
			wantRank:     RankExactName,
		},
		{
			desc:         "티커 전체 일치",
			query:        "005930",
			targetName:   "삼성전자",
			targetTicker: "005930",
			wantRank:     RankExactTicker,
		},
		{
			desc:         "이름과 티커 모두 일치 - 이름이 우선",
			query:        "200",
			targetName:   "KODEX 200",
			targetTicker: "200000",
			wantRank:     RankExactName,
		},
		{
			desc:         "5글자 쿼리 - maxErrors=2, 오타 2개 허용",
			query:        "삼성전기공", // "삼성전자공" 같은 오타 2개
			targetName:   "삼성전자공업",
			targetTicker: "000000",
			wantRank:     RankFuzzyName,
		},
		{
			desc:         "완전히 다른 종목 - RankNone",
			query:        "현대자동차",
			targetName:   "삼성전자",
			targetTicker: "005930",
			wantRank:     RankNone,
		},
		{
			desc:         "EvaluateMatch에 index가 반영됨",
			query:        "삼성",
			targetName:   "삼성전자",
			targetTicker: "005930",
			wantRank:     RankExactName, // index=42 이어도 Rank는 동일
		},
	}

	for _, tt := range tests {
		t.Run(tt.desc, func(t *testing.T) {
			got := EvaluateMatch(tt.query, tt.targetName, tt.targetTicker, 42)
			if got.Rank != tt.wantRank {
				t.Errorf("EvaluateMatch() Rank = %v, want %v", got.Rank, tt.wantRank)
			}
		})
	}
}

// TestEvaluateMatch_IndexPreserved EvaluateMatch가 반환하는 Index가 입력 i와 동일한지 확인한다.
func TestEvaluateMatch_IndexPreserved(t *testing.T) {
	result := EvaluateMatch("삼성", "삼성전자", "005930", 7)
	if result.Rank == RankNone {
		t.Fatal("expected match")
	}
	if result.Index != 7 {
		t.Errorf("expected Index=7, got %d", result.Index)
	}
}

// TestEvaluateMatch_RankNone_IndexIsZero 매칭 실패 시 Index는 의미 없음을 확인한다.
func TestEvaluateMatch_RankNone_IndexIsZero(t *testing.T) {
	result := EvaluateMatch("zzz", "삼성전자", "005930", 99)
	if result.Rank != RankNone {
		t.Fatalf("expected RankNone, got %v", result.Rank)
	}
	// RankNone 시 Index=0 (zero value) — 사용해선 안 됨
	if result.Index != 0 {
		t.Errorf("expected Index=0 on RankNone, got %d", result.Index)
	}
}

// TestEvaluateMatch_FuzzyDistanceReturned 퍼지 매칭 시 Distance 값이 0보다 크다.
func TestEvaluateMatch_FuzzyDistanceReturned(t *testing.T) {
	// "현대오투" → "현대오토에버" (오타 1개)
	result := EvaluateMatch("현대오투", "현대오토에버", "307950", 0)
	if result.Rank != RankFuzzyName {
		t.Fatalf("expected RankFuzzyName, got %v", result.Rank)
	}
	if result.Distance <= 0 {
		t.Errorf("expected Distance > 0 for fuzzy match, got %d", result.Distance)
	}
}
