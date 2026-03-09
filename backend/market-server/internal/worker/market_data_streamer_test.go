package worker

import (
	"context"
	"encoding/json"
	"testing"
	"time"

	"market-server/internal/service"
)

// newTestHub는 Run 루프 없이 HandleMessage/Broadcast만 사용하는 최소 허브를 생성한다.
func newTestHub() *service.WSHub {
	return service.NewWSHub(nil)
}

// makeSubscribedClient는 지정된 토픽을 구독하는 가짜 클라이언트를 생성하고 반환한다.
// ORDERBOOK 구독에는 userID를 비워두면 인증 거절되므로 userID를 반드시 설정해야 한다.
func makeSubscribedClient(hub *service.WSHub, topic, ticker, userID string) *service.WsClient {
	client := &service.WsClient{
		ID:   userID,
		Send: make(chan []byte, 10),
	}
	msgMap := map[string]string{
		"action": string(service.ActionSubscribe),
		"topic":  topic,
	}
	if ticker != "" {
		msgMap["ticker"] = ticker
	}
	msgBytes, _ := json.Marshal(msgMap)
	hub.HandleMessage(client, msgBytes)
	return client
}

// ─── handleTickMessage 테스트 ─────────────────────────────────────────────────

// TestHandleTickMessage_ValidJSON_Broadcasts 유효한 Tick JSON이 구독 클라이언트에게 브로드캐스트되는지 확인한다.
func TestHandleTickMessage_ValidJSON_Broadcasts(t *testing.T) {
	hub := newTestHub()
	client := makeSubscribedClient(hub, service.TopicTick, "005930", "")

	streamer := NewMarketDataStreamer(nil, hub, "", "")

	tickData, _ := json.Marshal(Tick{
		Ticker:       "005930",
		Name:         "삼성전자",
		CurrentPrice: 80000,
		ChangeRate:   1.25,
		AccVolume:    1000000,
	})

	if err := streamer.handleTickMessage(context.Background(), tickData); err != nil {
		t.Fatalf("예상치 못한 오류: %v", err)
	}

	select {
	case msg := <-client.Send:
		var payload map[string]interface{}
		if err := json.Unmarshal(msg, &payload); err != nil {
			t.Fatalf("페이로드 파싱 실패: %v", err)
		}
		if payload["topic"] != service.TopicTick {
			t.Errorf("topic 불일치: got %v, want %s", payload["topic"], service.TopicTick)
		}
		data, ok := payload["data"].(map[string]interface{})
		if !ok {
			t.Fatal("data 필드가 객체가 아님")
		}
		if data["ticker"] != "005930" {
			t.Errorf("ticker 불일치: got %v", data["ticker"])
		}
		if data["price"] != float64(80000) {
			t.Errorf("price 불일치: got %v", data["price"])
		}
	case <-time.After(100 * time.Millisecond):
		t.Fatal("100ms 내 메시지 미수신")
	}
}

// TestHandleTickMessage_InvalidJSON_ReturnsError 잘못된 JSON은 에러를 반환하고 브로드캐스트하지 않아야 한다.
func TestHandleTickMessage_InvalidJSON_ReturnsError(t *testing.T) {
	hub := newTestHub()
	client := makeSubscribedClient(hub, service.TopicTick, "005930", "")

	streamer := NewMarketDataStreamer(nil, hub, "", "")

	if err := streamer.handleTickMessage(context.Background(), []byte("not valid json")); err == nil {
		t.Fatal("잘못된 JSON인데 에러가 반환되지 않음")
	}

	// 브로드캐스트되지 않아야 한다
	select {
	case <-client.Send:
		t.Error("에러 발생 시 브로드캐스트되면 안 됨")
	default:
	}
}

// TestHandleTickMessage_NoSubscribers_NoPanic 구독자 없는 토픽에 tick 메시지가 와도 패닉이 없어야 한다.
func TestHandleTickMessage_NoSubscribers_NoPanic(t *testing.T) {
	hub := newTestHub()
	streamer := NewMarketDataStreamer(nil, hub, "", "")

	tickData, _ := json.Marshal(Tick{Ticker: "005930", CurrentPrice: 80000})

	if err := streamer.handleTickMessage(context.Background(), tickData); err != nil {
		t.Fatalf("예상치 못한 오류: %v", err)
	}
}

// ─── handleOrderbookMessage 테스트 ───────────────────────────────────────────

// TestHandleOrderbookMessage_ValidJSON_Broadcasts 유효한 Orderbook JSON이 인증된 구독 클라이언트에게 브로드캐스트되는지 확인한다.
func TestHandleOrderbookMessage_ValidJSON_Broadcasts(t *testing.T) {
	hub := newTestHub()
	// ORDERBOOK은 userID가 있어야 구독 가능
	client := makeSubscribedClient(hub, service.TopicOrderbook, "005930", "user-123")

	streamer := NewMarketDataStreamer(nil, hub, "", "")

	obData, _ := json.Marshal(Orderbook{
		Ticker:     "005930",
		Name:       "삼성전자",
		AskPrice1:  80100,
		AskVolume1: 500,
		BidPrice1:  80000,
		BidVolume1: 1000,
	})

	if err := streamer.handleOrderbookMessage(context.Background(), obData); err != nil {
		t.Fatalf("예상치 못한 오류: %v", err)
	}

	select {
	case msg := <-client.Send:
		var payload map[string]interface{}
		if err := json.Unmarshal(msg, &payload); err != nil {
			t.Fatalf("페이로드 파싱 실패: %v", err)
		}
		if payload["topic"] != service.TopicOrderbook {
			t.Errorf("topic 불일치: got %v, want %s", payload["topic"], service.TopicOrderbook)
		}
		data, ok := payload["data"].(map[string]interface{})
		if !ok {
			t.Fatal("data 필드가 객체가 아님")
		}
		if data["ticker"] != "005930" {
			t.Errorf("ticker 불일치: got %v", data["ticker"])
		}
	case <-time.After(100 * time.Millisecond):
		t.Fatal("100ms 내 메시지 미수신")
	}
}

// TestHandleOrderbookMessage_InvalidJSON_ReturnsError 잘못된 JSON은 에러를 반환하고 브로드캐스트하지 않아야 한다.
func TestHandleOrderbookMessage_InvalidJSON_ReturnsError(t *testing.T) {
	hub := newTestHub()
	client := makeSubscribedClient(hub, service.TopicOrderbook, "005930", "user-123")

	streamer := NewMarketDataStreamer(nil, hub, "", "")

	if err := streamer.handleOrderbookMessage(context.Background(), []byte("{bad json")); err == nil {
		t.Fatal("잘못된 JSON인데 에러가 반환되지 않음")
	}

	select {
	case <-client.Send:
		t.Error("에러 발생 시 브로드캐스트되면 안 됨")
	default:
	}
}

// TestHandleOrderbookMessage_UnauthorizedClient_NotReceived 비인증 클라이언트는 ORDERBOOK 구독이 거절되어 메시지를 받지 않아야 한다.
func TestHandleOrderbookMessage_UnauthorizedClient_NotReceived(t *testing.T) {
	hub := newTestHub()
	// userID 없이 ORDERBOOK 구독 시도 → 인증 거절, subClients에 등록되지 않음
	unauthorizedClient := makeSubscribedClient(hub, service.TopicOrderbook, "005930", "")

	streamer := NewMarketDataStreamer(nil, hub, "", "")

	obData, _ := json.Marshal(Orderbook{Ticker: "005930", AskPrice1: 80100})
	streamer.handleOrderbookMessage(context.Background(), obData) //nolint

	// 인증 거절되었으므로 브로드캐스트 메시지를 받으면 안 된다
	// (인증 거절 시 ERROR 메시지가 Send에 들어올 수 있으므로 그것 제외)
	select {
	case msg := <-unauthorizedClient.Send:
		var payload map[string]interface{}
		json.Unmarshal(msg, &payload)
		if payload["topic"] == service.TopicOrderbook {
			t.Error("인증 거절된 클라이언트가 ORDERBOOK 데이터를 수신함")
		}
		// ERROR 메시지는 허용 (인증 거절 응답)
	default:
		// 아무 메시지도 없으면 정상 (ERROR 메시지도 이미 소비됐을 수 있음)
	}
}
