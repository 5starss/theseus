package search

import (
	"math"
	"strings"
)

// MatchScoreType 검색 매칭 정확도 랭크를 나타내는 열거형
type MatchScoreType int

const (
	RankExactName MatchScoreType = iota // 0: 종목명 정확히 포함 (최고점)
	RankExactTicker                     // 1: 티커(종목코드) 포함
	RankFuzzyName                       // 2: 오타 유사 매칭
	RankNone                            // 3: 매칭 안됨 (결과 제외)
)

// SearchResult 검색 결과를 담는 구조체 (정렬 시 활용)
type SearchResult struct {
	Index        int            // 원본 데이터 슬라이스 내 인덱스
	Rank         MatchScoreType // 매칭 순위
	Distance     int            // 편집 거리
}

// Normalize 문자열에서 모든 공백을 제거하고 소문자로 변환
func Normalize(s string) string {
	s = strings.ReplaceAll(s, " ", "")
	return strings.ToLower(s)
}

// EvaluateMatch 검색어(query)와 대상 종목(name, ticker)을 비교하여 매칭 결과 도출
func EvaluateMatch(query, targetName, targetTicker string, i int) SearchResult {
	normName := Normalize(targetName)
	normTicker := Normalize(targetTicker)

	// 1순위: 종목명 부분 일치
	if strings.Contains(normName, query) {
		return SearchResult{Index: i, Rank: RankExactName, Distance: 0}
	}

	// 2순위: 티커 부분 일치
	if strings.Contains(normTicker, query) {
		return SearchResult{Index: i, Rank: RankExactTicker, Distance: 0}
	}

	// 3순위: 퍼지 매칭
	// query 길이에 따라 허용할 오타 수 결정 (2글자 이하는 오타 미허용)
	maxErrors := 0
	if utf8Len(query) >= 3 {
		maxErrors = 1
	}
	if utf8Len(query) >= 5 {
		maxErrors = 2
	}

	if maxErrors > 0 {
		dist, isMatch := fuzzySubstringMatch(query, normName, maxErrors)
		if isMatch {
			return SearchResult{Index: i, Rank: RankFuzzyName, Distance: dist}
		}
	}

	return SearchResult{Rank: RankNone}
}

func utf8Len(s string) int {
	return len([]rune(s))
}

// fuzzySubstringMatch 검색어가 대상 문자열의 "부분 문자열"과 얼마나 비슷한지 측정
func fuzzySubstringMatch(query, target string, maxErrors int) (int, bool) {
	qRunes := []rune(query)
	tRunes := []rune(target)
	qLen := len(qRunes)
	tLen := len(tRunes)

	if qLen == 0 || tLen == 0 {
		return 0, false
	}
	if qLen > tLen+maxErrors {
		return 0, false
	}

	minGlobalDistance := math.MaxInt32

	// 간단한 브루트포스 부분 문자열 Levenshtein
	// target 문자열을 순회하면서 qLen 정도의 윈도우를 잡아 편집거리 계산
	for i := 0; i <= tLen-qLen+maxErrors; i++ {
		for diff := -maxErrors; diff <= maxErrors; diff++ {
			endIdx := i + qLen + diff
			if endIdx < i || endIdx > tLen {
				continue
			}
			dist := levenshtein(qRunes, tRunes[i:endIdx])
			if dist < minGlobalDistance {
				minGlobalDistance = dist
			}
		}
	}

	return minGlobalDistance, minGlobalDistance <= maxErrors
}

func levenshtein(a, b []rune) int {
	lenA := len(a)
	lenB := len(b)

	dp := make([][]int, lenA+1)
	for i := range dp {
		dp[i] = make([]int, lenB+1)
	}

	for i := 0; i <= lenA; i++ {
		dp[i][0] = i
	}
	for j := 0; j <= lenB; j++ {
		dp[0][j] = j
	}

	for i := 1; i <= lenA; i++ {
		for j := 1; j <= lenB; j++ {
			cost := 1
			if a[i-1] == b[j-1] {
				cost = 0
			}
			dp[i][j] = min3(
				dp[i-1][j]+1,
				dp[i][j-1]+1,
				dp[i-1][j-1]+cost,
			)
		}
	}

	return dp[lenA][lenB]
}

func min3(a, b, c int) int {
	if a <= b && a <= c {
		return a
	}
	if b <= a && b <= c {
		return b
	}
	return c
}
