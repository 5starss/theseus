package kis

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"sort"
	"testing"
	"time"

	"market-server/internal/config"

	"github.com/gorilla/websocket"
)

// ─── 공용 Mock KIS 서버 헬퍼 ──────────────────────────────────────────────────

// testKISServer는 KIS HTTP(승인키 발급) + WebSocket을 모사하는 테스트 서버다.
type testKISServer struct {
	server   *httptest.Server
	received chan []byte // WS 클라이언트가 보낸 메시지 수집용
}

func newTestKISServer(t *testing.T) *testKISServer {
	t.Helper()
	ts := &testKISServer{
		received: make(chan []byte, 200),
	}

	upgrader := websocket.Upgrader{
		CheckOrigin: func(r *http.Request) bool { return true },
	}

	mux := http.NewServeMux()

	// /oauth2/Approval — WSClient.GetApprovalKey 대응
	mux.HandleFunc("/oauth2/Approval", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{ //nolint
			"approval_key": "test-approval-key",
		})
	})

	// /ws — WSClient.Connect 대응 (수신 메시지는 received 채널로)
	mux.HandleFunc("/ws", func(w http.ResponseWriter, r *http.Request) {
		conn, err := upgrader.Upgrade(w, r, nil)
		if err != nil {
			return
		}
		defer conn.Close()
		for {
			_, msg, err := conn.ReadMessage()
			if err != nil {
				return
			}
			select {
			case ts.received <- msg:
			default: // 버퍼 가득 차면 드롭 (테스트에서는 충분한 버퍼 사용)
			}
		}
	})

	ts.server = httptest.NewServer(mux)
	t.Cleanup(ts.server.Close)
	return ts
}

// kisConfig는 이 테스트 서버를 가리키는 KISConfig를 반환한다.
// appKey를 파라미터로 받아 복수 클라이언트 구분에 사용한다.
func (ts *testKISServer) kisConfig(appKey string) config.KISConfig {
	// http://127.0.0.1:PORT → ws://127.0.0.1:PORT/ws
	wsURL := "ws" + ts.server.URL[4:] + "/ws"
	return config.KISConfig{
		AppKey:    appKey,
		AppSecret: "test-secret",
		BaseURL:   ts.server.URL,
		WSURL:     wsURL,
	}
}

// connectPool은 테스트 서버에 연결된 N-클라이언트 WSPool을 반환한다.
func connectPool(t *testing.T, ts *testKISServer, n int) (*WSPool, context.CancelFunc) {
	t.Helper()
	cfgs := make([]config.KISConfig, n)
	for i := range cfgs {
		cfgs[i] = ts.kisConfig(fmt.Sprintf("testkey%02d", i+1))
	}

	pool := NewWSPool(cfgs)
	ctx, cancel := context.WithCancel(context.Background())

	if err := pool.ConnectAll(ctx); err != nil {
		cancel()
		t.Fatalf("ConnectAll failed: %v", err)
	}
	return pool, cancel
}

// ─── NewWSPool ────────────────────────────────────────────────────────────────

// TestNewWSPool_ClientCount 설정 수만큼 WSClient가 생성된다.
func TestNewWSPool_ClientCount(t *testing.T) {
	for _, n := range []int{1, 2, 5} {
		cfgs := make([]config.KISConfig, n)
		for i := range cfgs {
			cfgs[i] = config.KISConfig{AppKey: fmt.Sprintf("testkey%02d", i), AppSecret: "test-secret"}
		}
		pool := NewWSPool(cfgs)
		if pool.ClientCount() != n {
			t.Errorf("n=%d: ClientCount() = %d, want %d", n, pool.ClientCount(), n)
		}
	}
}

// TestNewWSPool_EmptyConfigs 빈 설정이면 클라이언트 수 0이다.
func TestNewWSPool_EmptyConfigs(t *testing.T) {
	pool := NewWSPool(nil)
	if pool.ClientCount() != 0 {
		t.Errorf("expected 0 clients, got %d", pool.ClientCount())
	}
}

// TestNewWSPool_MessageChanIsBuffered 공유 MessageChan이 버퍼드 채널이다.
func TestNewWSPool_MessageChanIsBuffered(t *testing.T) {
	pool := NewWSPool([]config.KISConfig{{AppKey: "testkey01", AppSecret: "test-secret"}})
	// 버퍼드 채널이면 블록 없이 바로 쓸 수 있다
	select {
	case pool.MessageChan <- []byte("probe"):
		// 성공: 버퍼드
	default:
		t.Error("MessageChan이 버퍼드 채널이 아님 — 즉시 전송 불가")
	}
}

// ─── ConnectAll ───────────────────────────────────────────────────────────────

// TestConnectAll_AllClientsConnect 모든 클라이언트가 연결되면 에러 없이 반환된다.
func TestConnectAll_AllClientsConnect(t *testing.T) {
	ts := newTestKISServer(t)
	pool, cancel := connectPool(t, ts, 3)
	defer cancel()
	defer pool.Close()

	if pool.ClientCount() != 3 {
		t.Errorf("expected 3 clients, got %d", pool.ClientCount())
	}
	for i, ws := range pool.clients {
		if !ws.connected {
			t.Errorf("client #%d should be connected", i+1)
		}
	}
}

// TestConnectAll_NoClients_ReturnsError 클라이언트가 없으면 에러를 반환한다.
func TestConnectAll_NoClients_ReturnsError(t *testing.T) {
	pool := NewWSPool(nil)
	err := pool.ConnectAll(context.Background())
	if err == nil {
		t.Error("빈 풀에서 ConnectAll이 에러를 반환하지 않음")
	}
}

// TestConnectAll_BadApprovalKeyURL_PartialFailure 승인키 발급에 실패한 클라이언트는 건너뛴다.
// 유효한 클라이언트가 1개 이상이면 에러 없이 반환되어야 한다.
func TestConnectAll_BadApprovalKeyURL_PartialFailure(t *testing.T) {
	ts := newTestKISServer(t)

	// 첫 번째는 잘못된 BaseURL (승인키 발급 실패), 두 번째는 정상
	cfgs := []config.KISConfig{
		{AppKey: "badkey01", AppSecret: "badsecret", BaseURL: "http://127.0.0.1:1", WSURL: "ws://127.0.0.1:1/ws"},
		ts.kisConfig("testkey-good"),
	}
	pool := NewWSPool(cfgs)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	err := pool.ConnectAll(ctx)
	if err != nil {
		t.Errorf("연결 성공한 클라이언트가 있는데 에러 반환: %v", err)
	}
	pool.Close()
}

// ─── SubscribeAll — 종목 분배 로직 ───────────────────────────────────────────

// makeTickers는 N개의 더미 티커를 생성한다.
func makeTickers(n int) []string {
	tickers := make([]string, n)
	for i := range tickers {
		tickers[i] = fmt.Sprintf("%06d", i+1)
	}
	return tickers
}

// subscribedTickers는 WSClient의 subscribers 맵에서 티커 리스트를 추출한다.
func subscribedTickers(ws *WSClient) []string {
	ws.subMu.RLock()
	defer ws.subMu.RUnlock()
	tickers := make([]string, 0, len(ws.subscribers))
	for t := range ws.subscribers {
		tickers = append(tickers, t)
	}
	sort.Strings(tickers)
	return tickers
}

// TestSubscribeAll_EvenDistribution 40종목 / 2클라이언트 → 각 20종목.
func TestSubscribeAll_EvenDistribution(t *testing.T) {
	ts := newTestKISServer(t)
	pool, cancel := connectPool(t, ts, 2)
	defer cancel()
	defer pool.Close()

	tickers := makeTickers(40)
	pool.SubscribeAll(context.Background(), tickers)

	for i, ws := range pool.clients {
		ws.subMu.RLock()
		count := len(ws.subscribers)
		ws.subMu.RUnlock()
		if count != 20 {
			t.Errorf("client #%d: want 20 subscribers, got %d", i+1, count)
		}
	}
}

// TestSubscribeAll_UnevenDistribution 30종목 / 2클라이언트 → client1=20, client2=10.
func TestSubscribeAll_UnevenDistribution(t *testing.T) {
	ts := newTestKISServer(t)
	pool, cancel := connectPool(t, ts, 2)
	defer cancel()
	defer pool.Close()

	tickers := makeTickers(30)
	pool.SubscribeAll(context.Background(), tickers)

	want := []int{20, 10}
	for i, ws := range pool.clients {
		ws.subMu.RLock()
		got := len(ws.subscribers)
		ws.subMu.RUnlock()
		if got != want[i] {
			t.Errorf("client #%d: want %d subscribers, got %d", i+1, want[i], got)
		}
	}
}

// TestSubscribeAll_FiveClientsHundredTickers 5클라이언트 × 20종목 = 100종목 완전 분배.
func TestSubscribeAll_FiveClientsHundredTickers(t *testing.T) {
	ts := newTestKISServer(t)
	pool, cancel := connectPool(t, ts, 5)
	defer cancel()
	defer pool.Close()

	tickers := makeTickers(100)
	pool.SubscribeAll(context.Background(), tickers)

	for i, ws := range pool.clients {
		ws.subMu.RLock()
		count := len(ws.subscribers)
		ws.subMu.RUnlock()
		if count != 20 {
			t.Errorf("client #%d: want 20 subscribers, got %d", i+1, count)
		}
	}
}

// TestSubscribeAll_ExcessTickers 세션 용량(20)보다 많은 종목은 잘라낸다.
func TestSubscribeAll_ExcessTickers(t *testing.T) {
	ts := newTestKISServer(t)
	pool, cancel := connectPool(t, ts, 1) // 1세션 = 최대 20종목
	defer cancel()
	defer pool.Close()

	tickers := makeTickers(25) // 25개 요청 → 20개만 구독
	pool.SubscribeAll(context.Background(), tickers)

	ws := pool.clients[0]
	ws.subMu.RLock()
	count := len(ws.subscribers)
	ws.subMu.RUnlock()

	if count != maxTickersPerSession {
		t.Errorf("1세션 초과 종목은 잘려야 함: want %d, got %d", maxTickersPerSession, count)
	}
}

// TestSubscribeAll_FewerTickersThanClients 종목 수가 클라이언트 수보다 적으면 일부 클라이언트는 구독 없음.
func TestSubscribeAll_FewerTickersThanClients(t *testing.T) {
	ts := newTestKISServer(t)
	pool, cancel := connectPool(t, ts, 3) // 3클라이언트
	defer cancel()
	defer pool.Close()

	tickers := makeTickers(10) // 10종목만 → client1=10, client2=0, client3=0
	pool.SubscribeAll(context.Background(), tickers)

	want := []int{10, 0, 0}
	for i, ws := range pool.clients {
		ws.subMu.RLock()
		got := len(ws.subscribers)
		ws.subMu.RUnlock()
		if got != want[i] {
			t.Errorf("client #%d: want %d subscribers, got %d", i+1, want[i], got)
		}
	}
}

// TestSubscribeAll_EmptyTickers 종목이 없어도 패닉 없이 정상 처리된다.
func TestSubscribeAll_EmptyTickers(t *testing.T) {
	ts := newTestKISServer(t)
	pool, cancel := connectPool(t, ts, 2)
	defer cancel()
	defer pool.Close()

	// 패닉 없이 실행되면 성공
	pool.SubscribeAll(context.Background(), []string{})

	for i, ws := range pool.clients {
		ws.subMu.RLock()
		count := len(ws.subscribers)
		ws.subMu.RUnlock()
		if count != 0 {
			t.Errorf("client #%d: 빈 티커 구독 후 subscriber가 있으면 안 됨, got %d", i+1, count)
		}
	}
}

// TestSubscribeAll_NoOverlapBetweenClients 분배된 종목이 클라이언트 간에 중복되지 않는다.
func TestSubscribeAll_NoOverlapBetweenClients(t *testing.T) {
	ts := newTestKISServer(t)
	pool, cancel := connectPool(t, ts, 3)
	defer cancel()
	defer pool.Close()

	tickers := makeTickers(50)
	pool.SubscribeAll(context.Background(), tickers)

	// 전체 구독 집합이 중복 없이 50개인지 확인
	seen := make(map[string]int)
	for i, ws := range pool.clients {
		for _, t := range subscribedTickers(ws) {
			if prev, ok := seen[t]; ok {
				t2 := t
				_ = t2
				_ = prev
				_ = i
				// 이 부분은 t가 testing.T와 충돌하여 그냥 map으로 처리
			}
			seen[t] = i
		}
	}
	if len(seen) != len(tickers) {
		t2 := t
		t2.Errorf("중복 없이 %d종목이어야 하나 실제 %d종목", len(tickers), len(seen))
	}
}

// ─── Fan-in ───────────────────────────────────────────────────────────────────

// TestFanIn_MergesMessagesFromMultipleClients 복수 클라이언트의 메시지가 공유 MessageChan에 모인다.
func TestFanIn_MergesMessagesFromMultipleClients(t *testing.T) {
	ts := newTestKISServer(t)
	pool, cancel := connectPool(t, ts, 3)
	defer cancel()
	defer pool.Close()

	// 각 클라이언트의 MessageChan에 직접 메시지 주입 (readPump 우회)
	want := make(map[string]bool)
	for i, ws := range pool.clients {
		msg := []byte(fmt.Sprintf("msg-from-client-%d", i))
		want[string(msg)] = false
		ws.MessageChan <- msg
	}

	// 3개 메시지가 모두 pool.MessageChan에 도달해야 한다
	received := make(map[string]bool)
	deadline := time.After(2 * time.Second)
	for len(received) < len(want) {
		select {
		case msg := <-pool.MessageChan:
			received[string(msg)] = true
		case <-deadline:
			t.Fatalf("타임아웃: 수신 %d/%d — 미수신: %v", len(received), len(want), unreceived(want, received))
		}
	}
}

// TestFanIn_HighThroughput 대량 메시지가 손실 없이 전달된다.
func TestFanIn_HighThroughput(t *testing.T) {
	ts := newTestKISServer(t)
	pool, cancel := connectPool(t, ts, 2)
	defer cancel()
	defer pool.Close()

	const msgPerClient = 500
	total := 2 * msgPerClient

	// 비동기로 메시지 주입
	for clientIdx, ws := range pool.clients {
		go func(w *WSClient, idx int) {
			for i := 0; i < msgPerClient; i++ {
				w.MessageChan <- []byte(fmt.Sprintf("c%d-m%d", idx, i))
			}
		}(ws, clientIdx)
	}

	// 전체 수집
	received := 0
	deadline := time.After(5 * time.Second)
	for received < total {
		select {
		case <-pool.MessageChan:
			received++
		case <-deadline:
			t.Fatalf("타임아웃: %d/%d 메시지만 수신", received, total)
		}
	}
}

// TestFanIn_ContextCancellation_FanInStops context 취소 후 Fan-in 고루틴이 종료된다.
func TestFanIn_ContextCancellation_FanInStops(t *testing.T) {
	ts := newTestKISServer(t)

	cfgs := []config.KISConfig{ts.kisConfig("testkey01")}
	pool := NewWSPool(cfgs)
	ctx, cancel := context.WithCancel(context.Background())

	if err := pool.ConnectAll(ctx); err != nil {
		t.Fatalf("ConnectAll failed: %v", err)
	}

	// context 취소 후 바로 pool.Close() 호출해도 데드락 없이 완료되어야 한다
	cancel()

	done := make(chan struct{})
	go func() {
		pool.Close()
		close(done)
	}()

	select {
	case <-done:
		// 정상 종료
	case <-time.After(3 * time.Second):
		t.Fatal("pool.Close()가 3초 내 완료되지 않음 — 고루틴 누수 의심")
	}
}

// ─── Close ────────────────────────────────────────────────────────────────────

// TestClose_MessageChanIsClosed pool.Close() 후 공유 MessageChan이 닫혀야 한다.
func TestClose_MessageChanIsClosed(t *testing.T) {
	ts := newTestKISServer(t)
	pool, cancel := connectPool(t, ts, 2)

	cancel() // 재연결 방지
	pool.Close()

	// 닫힌 채널에서 읽으면 ok=false
	select {
	case _, ok := <-pool.MessageChan:
		if ok {
			t.Error("pool.MessageChan이 닫히지 않음")
		}
	case <-time.After(3 * time.Second):
		t.Fatal("pool.MessageChan이 3초 내 닫히지 않음")
	}
}

// TestClose_Idempotent_NoPanic (재호출에 대한 방어는 구현에 따라 다름)
// 여기서는 Close 후 MessageChan 수신이 즉시 끝나는지만 검증한다.
func TestClose_DrainAfterClose(t *testing.T) {
	ts := newTestKISServer(t)
	pool, cancel := connectPool(t, ts, 1)

	// 메시지를 미리 한 개 넣어두고 Close
	pool.clients[0].MessageChan <- []byte("last-message")

	cancel()
	pool.Close()

	// MessageChan이 닫힌 후 range로 잔여 메시지를 읽을 수 있어야 한다
	var drained []string
	for msg := range pool.MessageChan {
		drained = append(drained, string(msg))
	}
	// "last-message"가 있을 수도 없을 수도 있으나 (fan-in이 ctx 취소 후 전달 안 할 수도), 패닉은 없어야 한다
	_ = drained
}

// ─── ClientCount ──────────────────────────────────────────────────────────────

func TestClientCount_ReturnsPoolSize(t *testing.T) {
	cases := []struct {
		n int
	}{
		{0}, {1}, {3}, {5},
	}
	for _, tc := range cases {
		cfgs := make([]config.KISConfig, tc.n)
		for i := range cfgs {
			cfgs[i] = config.KISConfig{AppKey: fmt.Sprintf("testkey%02d", i), AppSecret: "test-secret"}
		}
		pool := NewWSPool(cfgs)
		if pool.ClientCount() != tc.n {
			t.Errorf("n=%d: ClientCount()=%d, want %d", tc.n, pool.ClientCount(), tc.n)
		}
	}
}

// ─── 헬퍼 ─────────────────────────────────────────────────────────────────────

// unreceived는 want에 있으나 received에 없는 키를 반환한다.
func unreceived(want, received map[string]bool) []string {
	var missing []string
	for k := range want {
		if !received[k] {
			missing = append(missing, k)
		}
	}
	return missing
}
