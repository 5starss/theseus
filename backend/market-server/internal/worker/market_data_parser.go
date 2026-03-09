package worker

import (
	"strconv"
	"strings"
)

// Tick 실시간 주식 체결 데이터
type Tick struct {
	Ticker       string  `json:"ticker"`
	Name         string  `json:"name"`
	CurrentPrice float64 `json:"price"`
	OpenPrice    float64 `json:"open"`
	HighPrice    float64 `json:"high"`
	LowPrice     float64 `json:"low"`
	ChangeRate   float64 `json:"change_rate"`
	AccVolume    int64   `json:"acc_vol"`
}

// Orderbook 실시간 주식 호가 데이터
type Orderbook struct {
	Ticker     string  `json:"ticker"`
	Name       string  `json:"name"`
	AskPrice1  float64 `json:"askPrice1"`
	AskVolume1 int64   `json:"askVolume1"`
	BidPrice1  float64 `json:"bidPrice1"`
	BidVolume1 int64   `json:"bidVolume1"`
}

// parseKISMessage KIS의 Pipe(|) 심볼 구분자 포맷을 파싱한다.
func parseKISMessage(rawText string) (interface{}, string, error) {
	// 예: "1|H0STCNT0|001|005930^80500^1.25^15000000^..."
	// Data body는 4번째 파트(index 3)에 ^ 기호로 구분되어 들어온다.
	parts := strings.SplitN(rawText, "|", 4)
	if len(parts) < 4 {
		return nil, "", nil // Ping이나 제어 메시지 무시
	}

	trID := parts[1]
	bodyParts := strings.Split(parts[3], "^")

	if len(bodyParts) == 0 {
		return nil, "", nil
	}

	switch trID {
	case "H0STCNT0": // 국내주식 체결가
		if len(bodyParts) < 14 {
			return nil, "", nil
		}

		ticker := bodyParts[0]
		price, _ := strconv.ParseFloat(bodyParts[2], 64)
		open, _ := strconv.ParseFloat(bodyParts[7], 64)
		high, _ := strconv.ParseFloat(bodyParts[8], 64)
		low, _ := strconv.ParseFloat(bodyParts[9], 64)
		rate, _ := strconv.ParseFloat(bodyParts[5], 64)
		volume, _ := strconv.ParseInt(bodyParts[13], 10, 64)

		return Tick{
			Ticker:       ticker,
			Name:         Top40Stocks[ticker], // 메모리 Map에서 매핑
			CurrentPrice: price,
			OpenPrice:    open,
			HighPrice:    high,
			LowPrice:     low,
			ChangeRate:   rate,
			AccVolume:    volume,
		}, "tick", nil

	case "H0STASP0": // 국내주식 호가
		if len(bodyParts) < 43 {
			return nil, "", nil
		}

		ticker := bodyParts[0]
		askP1, _ := strconv.ParseFloat(bodyParts[3], 64)
		askV1, _ := strconv.ParseInt(bodyParts[23], 10, 64)
		bidP1, _ := strconv.ParseFloat(bodyParts[13], 64)   // 매수호가1
		bidV1, _ := strconv.ParseInt(bodyParts[33], 10, 64) // 매수호량1

		return Orderbook{
			Ticker:     ticker,
			Name:       Top40Stocks[ticker], // 메모리 Map에서 매핑
			AskPrice1:  askP1,
			AskVolume1: askV1,
			BidPrice1:  bidP1,
			BidVolume1: bidV1,
		}, "orderbook", nil
	}

	return nil, "", nil
}
