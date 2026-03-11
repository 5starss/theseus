package worker

// Top40Stocks 구독 대상 종목에 대한 티커와 종목명 매핑
// 메모리 상주 Map으로 API 파싱 시점에 종목명을 끼워넣기 위해 사용
var Top40Stocks = map[string]string{
	"005930": "삼성전자",
	"000660": "SK하이닉스",
	"005380": "현대차",
	"373220": "LG에너지솔루션",
	"207940": "삼성바이오로직스",
	"012450": "한화에어로스페이스",
	"034020": "두산에너빌리티",
	"329180": "HD현대중공업",
	"105560": "KB금융",
	"068270": "셀트리온",
	"028260": "삼성물산",
	"055550": "신한지주",
	"032830": "삼성생명",
	"042660": "한화오션",
	"012330": "현대모비스",
	"035420": "NAVER",
	"006400": "삼성SDI",
	"042700": "한미반도체",
	"122630": "KODEX 레버리지",
	"252670": "KODEX 200선물인버스2X",
}

// GetTop40Tickers 구독 대상 종목의 티커 리스트만 반환한다 (웹소켓 구독용)
func GetTop40Tickers() []string {
	tickers := make([]string, 0, len(Top40Stocks))
	for ticker := range Top40Stocks {
		tickers = append(tickers, ticker)
	}
	return tickers
}
