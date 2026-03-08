package handler

import (
	"context"
	"encoding/json"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/alicebob/miniredis/v2"
	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
	"github.com/redis/go-redis/v9"
	"market-server/internal/domain"
	"market-server/internal/repository"
	"market-server/internal/service"
)

// dialWS는 테스트 서버에 WebSocket 클라이언트를 연결한다.
func dialWS(t *testing.T, ts *httptest.Server) *websocket.Conn {
	t.Helper()
	wsURL := "ws" + strings.TrimPrefix(ts.URL, "http") + "/v1/stocks/ws"
	conn, _, err := websocket.DefaultDialer.Dial(wsURL, nil)
	if err != nil {
		t.Fatalf("WebSocket 연결 실패: %v", err)
	}
	t.Cleanup(func() { conn.Close() })
	return conn
}

// newFullWSEnv는 테스트 서버까지 포함한 완전한 환경을 반환한다.
func newFullWSEnv(t *testing.T) (*httptest.Server, *service.WSHub, *miniredis.Miniredis, *repository.StockRepository) {
	t.Helper()

	mr, err := miniredis.Run()
	if err != nil {
		t.Fatalf("miniredis start failed: %v", err)
	}
	t.Cleanup(mr.Close)

	rdb := redis.NewClient(&redis.Options{Addr: mr.Addr()})
	repo := repository.NewStockRepository(rdb, nil)
	svc := service.NewStockService(repo, nil)

	hub := service.NewWSHub(svc)
	ctx, cancel := context.WithCancel(context.Background())
	go hub.Run(ctx)
	t.Cleanup(cancel)

	r := gin.New()
	wsH := NewWSHandler(hub)
	r.GET("/v1/stocks/ws", wsH.ServeWS)

	ts := httptest.NewServer(r)
	t.Cleanup(ts.Close)

	return ts, hub, mr, repo
}

// ─── 연결 업그레이드 테스트 ────────────────────────────────────────────────────

// TestWSConnect_Upgrade WebSocket 핸드쉐이크가 정상적으로 이루어지는지 확인한다.
func TestWSConnect_Upgrade(t *testing.T) {
	ts, _, _, _ := newFullWSEnv(t)

	conn := dialWS(t, ts)

	// 정상 연결 확인: ping 메시지를 보내고 응답이 없어도 연결이 살아있으면 성공
	if conn == nil {
		t.Fatal("예상치 못한 nil 연결")
	}
}

// ─── SUBSCRIBE 테스트 ─────────────────────────────────────────────────────────

// TestWSSubscribe_HOME_40 HOME_40 토픽 구독 후 0.5초 내 배치 데이터를 수신하는지 확인한다.
func TestWSSubscribe_HOME_40(t *testing.T) {
	ts, _, mr, repo := newFullWSEnv(t)

	// Redis에 종목 데이터 세팅
	stocks := []*domain.Stock{
		{Ticker: "005930", Name: "삼성전자", CurrentPrice: 70000, ChangeRate: 1.5, AccVolume: 3000000},
		{Ticker: "000660", Name: "SK하이닉스", CurrentPrice: 180000, ChangeRate: -0.5, AccVolume: 5000000},
	}
	if err := repo.BulkUpsertStocks(context.Background(), stocks); err != nil {
		t.Fatalf("seed stocks failed: %v", err)
	}
	_ = mr

	conn := dialWS(t, ts)

	// SUBSCRIBE 메시지 전송
	subMsg, _ := json.Marshal(map[string]string{
		"action": "SUBSCRIBE",
		"topic":  "HOME_40",
	})
	if err := conn.WriteMessage(websocket.TextMessage, subMsg); err != nil {
		t.Fatalf("SUBSCRIBE 전송 실패: %v", err)
	}

	// 0.7초 내 데이터 수신 대기 (브로드캐스터 주기 0.5초)
	conn.SetReadDeadline(time.Now().Add(700 * time.Millisecond))
	_, data, err := conn.ReadMessage()
	if err != nil {
		t.Fatalf("데이터 수신 실패 (0.7초 내 메시지 없음): %v", err)
	}

	// 수신 메시지 검증
	var msg map[string]interface{}
	if err := json.Unmarshal(data, &msg); err != nil {
		t.Fatalf("메시지 파싱 실패: %v", err)
	}

	topic, ok := msg["topic"].(string)
	if !ok || topic != "HOME_40" {
		t.Errorf("topic 필드 오류: got %v", msg["topic"])
	}

	dataArr, ok := msg["data"].([]interface{})
	if !ok {
		t.Fatalf("data 필드가 배열이 아님: %T", msg["data"])
	}
	if len(dataArr) == 0 {
		t.Error("data 배열이 비어있음")
	}
}

// TestWSSubscribe_HOME_40_EmptyRedis Redis가 비어있을 때도 빈 배열로 정상 응답하는지 확인한다.
func TestWSSubscribe_HOME_40_EmptyRedis(t *testing.T) {
	ts, _, _, _ := newFullWSEnv(t)

	conn := dialWS(t, ts)

	subMsg, _ := json.Marshal(map[string]string{
		"action": "SUBSCRIBE",
		"topic":  "HOME_40",
	})
	if err := conn.WriteMessage(websocket.TextMessage, subMsg); err != nil {
		t.Fatalf("SUBSCRIBE 전송 실패: %v", err)
	}

	conn.SetReadDeadline(time.Now().Add(700 * time.Millisecond))
	_, data, err := conn.ReadMessage()
	if err != nil {
		t.Fatalf("데이터 수신 실패: %v", err)
	}

	var msg map[string]interface{}
	if err := json.Unmarshal(data, &msg); err != nil {
		t.Fatalf("메시지 파싱 실패: %v", err)
	}

	if msg["topic"] != "HOME_40" {
		t.Errorf("topic 오류: got %v", msg["topic"])
	}
	// 빈 Redis여도 topic과 data(빈 배열) 필드는 존재해야 함
	if _, ok := msg["data"]; !ok {
		t.Error("data 필드가 없음")
	}
}

// TestWSSubscribe_ORDERBOOK ORDERBOOK 토픽 구독 시 즉시 스냅샷을 받지는 않지만 구독 처리가 오류 없이 되어야 한다.
// (Phase 4: ORDERBOOK 실시간 push는 KIS WS 연동 시 동작, 현재는 구독 등록만 테스트)
func TestWSSubscribe_ORDERBOOK(t *testing.T) {
	ts, _, _, _ := newFullWSEnv(t)

	conn := dialWS(t, ts)

	subMsg, _ := json.Marshal(map[string]string{
		"action": "SUBSCRIBE",
		"topic":  "ORDERBOOK",
		"ticker": "005930",
	})
	if err := conn.WriteMessage(websocket.TextMessage, subMsg); err != nil {
		t.Fatalf("ORDERBOOK SUBSCRIBE 전송 실패: %v", err)
	}

	// ORDERBOOK은 push 브로드캐스터가 없으므로 즉시 데이터는 없다
	// 연결이 끊기지 않고 살아있는지만 확인
	conn.SetReadDeadline(time.Now().Add(300 * time.Millisecond))
	_, _, err := conn.ReadMessage()
	if err != nil {
		// deadline 초과(timeout)은 정상 — 연결은 유지되고 있다는 뜻
		if !strings.Contains(err.Error(), "timeout") && !strings.Contains(err.Error(), "deadline") {
			t.Errorf("예상치 못한 오류: %v", err)
		}
	}
}

// ─── UNSUBSCRIBE 테스트 ───────────────────────────────────────────────────────

// TestWSUnsubscribe_HOME_40 구독 후 해지하면 더 이상 데이터가 오지 않는지 확인한다.
func TestWSUnsubscribe_HOME_40(t *testing.T) {
	ts, _, _, repo := newFullWSEnv(t)

	stocks := []*domain.Stock{
		{Ticker: "005930", Name: "삼성전자", CurrentPrice: 70000, ChangeRate: 1.5, AccVolume: 3000000},
	}
	if err := repo.BulkUpsertStocks(context.Background(), stocks); err != nil {
		t.Fatalf("seed stocks failed: %v", err)
	}

	conn := dialWS(t, ts)

	// 1. 구독
	subMsg, _ := json.Marshal(map[string]string{"action": "SUBSCRIBE", "topic": "HOME_40"})
	conn.WriteMessage(websocket.TextMessage, subMsg)

	// 2. 첫 번째 메시지 수신 확인
	conn.SetReadDeadline(time.Now().Add(700 * time.Millisecond))
	_, _, err := conn.ReadMessage()
	if err != nil {
		t.Fatalf("첫 번째 메시지 수신 실패: %v", err)
	}

	// 3. 구독 해지
	unsubMsg, _ := json.Marshal(map[string]string{"action": "UNSUBSCRIBE", "topic": "HOME_40"})
	conn.WriteMessage(websocket.TextMessage, unsubMsg)

	// 4. 해지 후 1초 대기 — 더 이상 메시지가 오면 안 됨
	conn.SetReadDeadline(time.Now().Add(1 * time.Second))
	_, _, err = conn.ReadMessage()
	if err == nil {
		// 메시지가 왔다면: 구독 해지 직전 배치가 아직 전송 중일 수 있으므로
		// 한 번 더 확인 (두 번째 메시지가 와선 안 됨)
		conn.SetReadDeadline(time.Now().Add(700 * time.Millisecond))
		_, _, err2 := conn.ReadMessage()
		if err2 == nil {
			t.Error("UNSUBSCRIBE 후에도 계속 메시지가 수신됨 — 구독 해지 실패")
		}
	}
	// timeout 오류는 정상 (구독 해지 후 메시지 없음)
}

// ─── 잘못된 메시지 처리 테스트 ──────────────────────────────────────────────

// TestWSInvalidMessage_MalformedJSON 잘못된 JSON을 보내도 연결이 끊기지 않아야 한다.
func TestWSInvalidMessage_MalformedJSON(t *testing.T) {
	ts, _, _, _ := newFullWSEnv(t)

	conn := dialWS(t, ts)

	// 잘못된 JSON 전송
	conn.WriteMessage(websocket.TextMessage, []byte("not-json"))

	// 연결이 여전히 살아있는지 확인 — 유효한 메시지를 이후에도 처리 가능해야 함
	validMsg, _ := json.Marshal(map[string]string{"action": "SUBSCRIBE", "topic": "HOME_40"})
	if err := conn.WriteMessage(websocket.TextMessage, validMsg); err != nil {
		t.Errorf("잘못된 JSON 이후 연결이 끊김: %v", err)
	}
}

// TestWSInvalidMessage_MissingTicker ORDERBOOK 구독 시 ticker 없이 보내면 무시되어야 한다.
func TestWSInvalidMessage_MissingTicker(t *testing.T) {
	ts, _, _, _ := newFullWSEnv(t)

	conn := dialWS(t, ts)

	// ticker 없이 ORDERBOOK 구독 시도
	subMsg, _ := json.Marshal(map[string]string{"action": "SUBSCRIBE", "topic": "ORDERBOOK"})
	conn.WriteMessage(websocket.TextMessage, subMsg)

	// 연결 유지 확인
	conn.SetReadDeadline(time.Now().Add(300 * time.Millisecond))
	_, _, err := conn.ReadMessage()
	// timeout은 정상 (무시되어 응답 없음)
	if err != nil && !strings.Contains(err.Error(), "timeout") && !strings.Contains(err.Error(), "deadline") {
		t.Errorf("예상치 못한 연결 종료: %v", err)
	}
}

// ─── 배치 브로드캐스트 주기 테스트 ────────────────────────────────────────────

// TestWSBatchInterval HOME_40 브로드캐스트가 ~0.5초 간격으로 오는지 확인한다.
func TestWSBatchInterval(t *testing.T) {
	ts, _, _, repo := newFullWSEnv(t)

	stocks := []*domain.Stock{
		{Ticker: "005930", Name: "삼성전자", CurrentPrice: 70000, ChangeRate: 1.5, AccVolume: 3000000},
	}
	repo.BulkUpsertStocks(context.Background(), stocks)

	conn := dialWS(t, ts)

	subMsg, _ := json.Marshal(map[string]string{"action": "SUBSCRIBE", "topic": "HOME_40"})
	conn.WriteMessage(websocket.TextMessage, subMsg)

	// 첫 번째 메시지 수신 시각
	conn.SetReadDeadline(time.Now().Add(700 * time.Millisecond))
	_, _, err := conn.ReadMessage()
	if err != nil {
		t.Fatalf("첫 번째 메시지 수신 실패: %v", err)
	}
	t1 := time.Now()

	// 두 번째 메시지 수신 시각
	conn.SetReadDeadline(time.Now().Add(700 * time.Millisecond))
	_, _, err = conn.ReadMessage()
	if err != nil {
		t.Fatalf("두 번째 메시지 수신 실패: %v", err)
	}
	t2 := time.Now()

	interval := t2.Sub(t1)
	// 배치 주기 0.5초 ± 200ms 허용
	if interval < 300*time.Millisecond || interval > 700*time.Millisecond {
		t.Errorf("배치 간격이 비정상: %v (기대: 300ms~700ms)", interval)
	}
}

// ─── 다중 클라이언트 테스트 ────────────────────────────────────────────────────

// TestWSMultipleClients 여러 클라이언트가 동시에 구독해도 모두 데이터를 받아야 한다.
func TestWSMultipleClients(t *testing.T) {
	ts, _, _, repo := newFullWSEnv(t)

	stocks := []*domain.Stock{
		{Ticker: "005930", Name: "삼성전자", CurrentPrice: 70000, ChangeRate: 1.5, AccVolume: 3000000},
	}
	repo.BulkUpsertStocks(context.Background(), stocks)

	const numClients = 3
	conns := make([]*websocket.Conn, numClients)
	for i := 0; i < numClients; i++ {
		conns[i] = dialWS(t, ts)
	}

	// 모든 클라이언트 구독
	subMsg, _ := json.Marshal(map[string]string{"action": "SUBSCRIBE", "topic": "HOME_40"})
	for _, conn := range conns {
		if err := conn.WriteMessage(websocket.TextMessage, subMsg); err != nil {
			t.Fatalf("SUBSCRIBE 전송 실패: %v", err)
		}
	}

	// 모든 클라이언트가 데이터를 수신하는지 확인
	for i, conn := range conns {
		conn.SetReadDeadline(time.Now().Add(700 * time.Millisecond))
		_, data, err := conn.ReadMessage()
		if err != nil {
			t.Errorf("클라이언트 %d 데이터 수신 실패: %v", i, err)
			continue
		}
		var msg map[string]interface{}
		if json.Unmarshal(data, &msg) != nil || msg["topic"] != "HOME_40" {
			t.Errorf("클라이언트 %d 잘못된 메시지: %s", i, data)
		}
	}
}
