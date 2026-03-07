package domain

// RankType 종목 순위 기준
type RankType string

const RankTypeVolume RankType = "VOLUME" // 거래량 기준

// Stock 종목 도메인 모델
type Stock struct {
	Ticker       string  `json:"ticker"`       // 종목코드
	Name         string  `json:"name"`         // 종목명
	CurrentPrice int64   `json:"currentPrice"` // 현재가
	ChangeRate   float64 `json:"changeRate"`   // 전일 대비 등락률(%)
	AccVolume    int64   `json:"accVolume"`    // 누적 거래량
}

// Candle 캔들(차트) 도메인 모델
type Candle struct {
	Timestamp string `json:"timestamp"` // 시간
	Open      int64  `json:"open"`      // 시가
	High      int64  `json:"high"`      // 고가
	Low       int64  `json:"low"`       // 저가
	Close     int64  `json:"close"`     // 종가
	Volume    int64  `json:"volume"`    // 거래량
}
