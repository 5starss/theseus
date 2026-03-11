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

// OrderbookResponse 호가창 스냅샷 응답 모델 (현재가 포함)
type OrderbookResponse struct {
	Ticker       string  `json:"ticker"`
	Name         string  `json:"name"`
	CurrentPrice float64 `json:"currentPrice"`
	ChangeRate   float64 `json:"changeRate"`
	AskPrice1    float64 `json:"askPrice1"`
	AskVolume1   int64   `json:"askVolume1"`
	BidPrice1    float64 `json:"bidPrice1"`
	BidVolume1   int64   `json:"bidVolume1"`
}

// TickSnapshotResponse 상세 종목 실시간 체결 스냅샷 응답 모델
type TickSnapshotResponse struct {
	Ticker       string  `json:"ticker"`       // 종목코드
	Name         string  `json:"name"`         // 종목명
	CurrentPrice float64 `json:"currentPrice"` // 현재가
	ChangeRate   float64 `json:"changeRate"`   // 전일 대비 등락률(%)
	OpenPrice    float64 `json:"openPrice"`    // 시가
	HighPrice    float64 `json:"highPrice"`    // 고가
	LowPrice     float64 `json:"lowPrice"`     // 저가
	TradeVolume  int64   `json:"tradeVolume"`  // 단일 체결량 (추가됨)
	AccVolume    int64   `json:"accVolume"`    // 누적 거래량
}

