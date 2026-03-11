package worker

import (
	"testing"
)

// KIS 메시지 포맷: "recvSeq|trID|dataCount|body"
// body는 ^ 구분자로 각 필드를 나열한다.
// H0STCNT0 body 인덱스:
//   [0]  ticker
//   [2]  현재가
//   [5]  등락율
//   [7]  시가
//   [8]  고가
//   [9]  저가
//   [12] 단일 체결량 (trade_vol)
//   [13] 누적 거래량 (acc_vol)

// makeTickBody는 지정한 인덱스에 값을 세팅한 ^ 구분 body 문자열을 만든다.
func makeTickBody(fields map[int]string) string {
	parts := make([]string, 14)
	for i := range parts {
		if v, ok := fields[i]; ok {
			parts[i] = v
		} else {
			parts[i] = "0"
		}
	}
	result := ""
	for i, p := range parts {
		if i > 0 {
			result += "^"
		}
		result += p
	}
	return result
}

// ─── parseKISMessage - H0STCNT0 (체결가) ─────────────────────────────────────

// TestParseKISMessage_Tick_ParsesAllFields 모든 필드가 올바르게 파싱되는지 확인한다.
func TestParseKISMessage_Tick_ParsesAllFields(t *testing.T) {
	body := makeTickBody(map[int]string{
		0:  "005930",
		2:  "80500",
		5:  "1.25",
		7:  "80000",
		8:  "81000",
		9:  "79500",
		12: "500",
		13: "1500000",
	})
	raw := "1|H0STCNT0|001|" + body

	result, kind, err := parseKISMessage(raw)

	if err != nil {
		t.Fatalf("예상치 못한 오류: %v", err)
	}
	if kind != "tick" {
		t.Fatalf("kind 불일치: got %q, want %q", kind, "tick")
	}
	tick, ok := result.(Tick)
	if !ok {
		t.Fatal("결과가 Tick 타입이 아님")
	}

	if tick.Ticker != "005930" {
		t.Errorf("Ticker: got %q, want %q", tick.Ticker, "005930")
	}
	if tick.CurrentPrice != 80500 {
		t.Errorf("CurrentPrice: got %v, want 80500", tick.CurrentPrice)
	}
	if tick.ChangeRate != 1.25 {
		t.Errorf("ChangeRate: got %v, want 1.25", tick.ChangeRate)
	}
	if tick.OpenPrice != 80000 {
		t.Errorf("OpenPrice: got %v, want 80000", tick.OpenPrice)
	}
	if tick.HighPrice != 81000 {
		t.Errorf("HighPrice: got %v, want 81000", tick.HighPrice)
	}
	if tick.LowPrice != 79500 {
		t.Errorf("LowPrice: got %v, want 79500", tick.LowPrice)
	}
	if tick.TradeVolume != 500 {
		t.Errorf("TradeVolume: got %v, want 500", tick.TradeVolume)
	}
	if tick.AccVolume != 1500000 {
		t.Errorf("AccVolume: got %v, want 1500000", tick.AccVolume)
	}
}

// TestParseKISMessage_Tick_TradeVolumeIsDistinctFromAccVolume 단일 체결량과 누적 거래량이 독립적으로 파싱됨을 확인한다.
func TestParseKISMessage_Tick_TradeVolumeIsDistinctFromAccVolume(t *testing.T) {
	body := makeTickBody(map[int]string{
		0:  "005930",
		2:  "80500",
		12: "100",   // 단일 체결량
		13: "999999", // 누적 거래량
	})
	raw := "1|H0STCNT0|001|" + body

	result, _, _ := parseKISMessage(raw)
	tick := result.(Tick)

	if tick.TradeVolume == tick.AccVolume {
		t.Errorf("TradeVolume(%d)과 AccVolume(%d)이 같음 — 파싱 인덱스 혼동 의심", tick.TradeVolume, tick.AccVolume)
	}
	if tick.TradeVolume != 100 {
		t.Errorf("TradeVolume: got %v, want 100", tick.TradeVolume)
	}
	if tick.AccVolume != 999999 {
		t.Errorf("AccVolume: got %v, want 999999", tick.AccVolume)
	}
}

// TestParseKISMessage_Tick_ZeroTradeVolume 단일 체결량이 0인 경우도 정상 파싱되어야 한다.
func TestParseKISMessage_Tick_ZeroTradeVolume(t *testing.T) {
	body := makeTickBody(map[int]string{
		0:  "005930",
		2:  "80500",
		12: "0",
		13: "500000",
	})
	raw := "1|H0STCNT0|001|" + body

	result, kind, err := parseKISMessage(raw)
	if err != nil || kind != "tick" {
		t.Fatalf("err=%v, kind=%q", err, kind)
	}
	tick := result.(Tick)
	if tick.TradeVolume != 0 {
		t.Errorf("TradeVolume: got %v, want 0", tick.TradeVolume)
	}
}

// TestParseKISMessage_Tick_TooFewFields body 파트가 14개 미만이면 nil, "" 반환해야 한다.
func TestParseKISMessage_Tick_TooFewFields(t *testing.T) {
	raw := "1|H0STCNT0|001|005930^80500^1.25"

	result, kind, err := parseKISMessage(raw)

	if err != nil {
		t.Fatalf("예상치 못한 오류: %v", err)
	}
	if result != nil || kind != "" {
		t.Errorf("필드 부족 시 nil 반환 기대: got result=%v, kind=%q", result, kind)
	}
}

// ─── parseKISMessage - 제어 메시지 / 알 수 없는 trID ─────────────────────────

// TestParseKISMessage_ControlMessage_ReturnsNil pipe 구분자가 4개 미만이면 nil 반환해야 한다.
func TestParseKISMessage_ControlMessage_ReturnsNil(t *testing.T) {
	raw := "PING"

	result, kind, err := parseKISMessage(raw)

	if err != nil || result != nil || kind != "" {
		t.Errorf("제어 메시지 무시 기대: got result=%v, kind=%q, err=%v", result, kind, err)
	}
}

// TestParseKISMessage_UnknownTrID_ReturnsNil 알 수 없는 trID는 nil 반환해야 한다.
func TestParseKISMessage_UnknownTrID_ReturnsNil(t *testing.T) {
	raw := "1|UNKNOWN|001|a^b^c^d^e^f^g^h^i^j^k^l^m^n"

	result, kind, err := parseKISMessage(raw)

	if err != nil || result != nil || kind != "" {
		t.Errorf("알 수 없는 trID 무시 기대: got result=%v, kind=%q, err=%v", result, kind, err)
	}
}

// ─── parseKISMessage - H0STASP0 (호가) ───────────────────────────────────────

// makeOrderbookBody는 H0STASP0 body를 만든다 (최소 43개 필드 필요).
func makeOrderbookBody(fields map[int]string) string {
	parts := make([]string, 43)
	for i := range parts {
		if v, ok := fields[i]; ok {
			parts[i] = v
		} else {
			parts[i] = "0"
		}
	}
	result := ""
	for i, p := range parts {
		if i > 0 {
			result += "^"
		}
		result += p
	}
	return result
}

// TestParseKISMessage_Orderbook_ParsesFields 호가 메시지가 올바르게 파싱되는지 확인한다.
func TestParseKISMessage_Orderbook_ParsesFields(t *testing.T) {
	body := makeOrderbookBody(map[int]string{
		0:  "005930",
		3:  "80100", // 매도호가1
		13: "80000", // 매수호가1
		23: "500",   // 매도호량1
		33: "1000",  // 매수호량1
	})
	raw := "1|H0STASP0|001|" + body

	result, kind, err := parseKISMessage(raw)

	if err != nil {
		t.Fatalf("예상치 못한 오류: %v", err)
	}
	if kind != "orderbook" {
		t.Fatalf("kind 불일치: got %q, want %q", kind, "orderbook")
	}
	ob, ok := result.(Orderbook)
	if !ok {
		t.Fatal("결과가 Orderbook 타입이 아님")
	}
	if ob.Ticker != "005930" {
		t.Errorf("Ticker: got %q, want %q", ob.Ticker, "005930")
	}
	if ob.AskPrice1 != 80100 {
		t.Errorf("AskPrice1: got %v, want 80100", ob.AskPrice1)
	}
	if ob.BidPrice1 != 80000 {
		t.Errorf("BidPrice1: got %v, want 80000", ob.BidPrice1)
	}
	if ob.AskVolume1 != 500 {
		t.Errorf("AskVolume1: got %v, want 500", ob.AskVolume1)
	}
	if ob.BidVolume1 != 1000 {
		t.Errorf("BidVolume1: got %v, want 1000", ob.BidVolume1)
	}
}
