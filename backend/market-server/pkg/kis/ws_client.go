package kis

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"sync"
	"time"

	"market-server/internal/config"

	"github.com/gorilla/websocket"
)

// WsMessage KIS WebSocket 수신 원시 메시지 (Ping/Pong 등 제어 메시지 포함될 수 있음)
type WsMessage struct {
	Data []byte
}

type WSClient struct {
	cfg         config.KISConfig
	approvalKey string

	conn *websocket.Conn
	mu   sync.Mutex // Conn 동시 접근 보호 (Write)

	// MessageChan KIS에서 수신된 Raw 데이터를 파서(Worker)로 전달하는 버퍼드 채널 (Backpressure 방어)
	MessageChan chan []byte

	connected    bool
	noReconnect  bool                // "ALREADY IN USE" 등 재연결 불가 에러 수신 시 true
	reconnecting bool                // autoReconnect 중복 실행 방지
	subscribers  map[string]struct{} // reconnect 시 재구독용 저장소
	subMu        sync.RWMutex
}

func NewWSClient(cfg config.KISConfig) *WSClient {
	return &WSClient{
		cfg:         cfg,
		MessageChan: make(chan []byte, 5000), // 장 시작 시간대 Traffic Burst 대비 버퍼링 (배압 제어)
		subscribers: make(map[string]struct{}),
	}
}

// GetApprovalKey 실시간(WebSocket) 접속 키(Approval Key) 발급
func (w *WSClient) GetApprovalKey(ctx context.Context) error {
	body, _ := json.Marshal(map[string]string{
		"grant_type": "client_credentials",
		"appkey":     w.cfg.AppKey,
		"secretkey":  w.cfg.AppSecret,
	})

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, w.cfg.BaseURL+"/oauth2/Approval", bytes.NewReader(body))
	if err != nil {
		return fmt.Errorf("create approval request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json; utf-8")

	client := &http.Client{Timeout: 15 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("do approval request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("approval request status: %d", resp.StatusCode)
	}

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("read approval response: %w", err)
	}

	var res map[string]interface{}
	if err := json.Unmarshal(data, &res); err != nil {
		return fmt.Errorf("decode approval response: %w", err)
	}

	key, ok := res["approval_key"].(string)
	if !ok || key == "" {
		return fmt.Errorf("approval key not found in response: %s", string(data))
	}

	w.approvalKey = key
	log.Printf("Successfully acquired KIS WS Approval Key")
	return nil
}

// Connect WebSocket 서버에 단일 연결하고 수신 루프를 시작한다.
// 체결가(H0STCNT0)와 호가(H0STASP0)를 하나의 커넥션에서 모두 처리한다.
func (w *WSClient) Connect(ctx context.Context) error {
	w.mu.Lock()
	defer w.mu.Unlock()

	if w.connected {
		return nil
	}

	conn, _, err := websocket.DefaultDialer.DialContext(ctx, w.cfg.WSURL, nil)
	if err != nil {
		return fmt.Errorf("websocket dial: %w", err)
	}
	w.conn = conn
	w.connected = true

	go w.readPump(ctx)

	log.Printf("Connected to KIS WebSocket: %s", w.cfg.WSURL)
	return nil
}

// readPump KIS로부터 들어오는 메시지를 지속적으로 읽어 MessageChan으로 전달한다.
func (w *WSClient) readPump(ctx context.Context) {
	var rawCount int64
	defer func() {
		log.Printf("readPump exiting. total raw messages received: %d", rawCount)
	}()
	defer func() {
		w.mu.Lock()
		w.connected = false
		if w.conn != nil {
			w.conn.Close()
			w.conn = nil
		}
		noReconnect := w.noReconnect
		// 중복 autoReconnect 방지
		if !w.reconnecting && !noReconnect {
			w.reconnecting = true
		} else {
			noReconnect = true // 이미 재연결 중이거나 불가 상태면 스킵
		}
		w.mu.Unlock()

		if noReconnect {
			log.Printf("KIS WS: 재연결 중단 (복구 불가 에러 또는 이미 재연결 중)")
			return
		}
		go w.autoReconnect(ctx)
	}()

	for {
		select {
		case <-ctx.Done():
			return
		default:
			w.mu.Lock()
			conn := w.conn
			w.mu.Unlock()
			if conn == nil {
				return
			}

			_, msg, err := conn.ReadMessage()
			if err != nil {
				log.Printf("KIS WS Read Error: %v", err)
				return // defer 블록 실행 -> 재연결 시도
			}

			// KIS Ping 메시지 ("PINGPONG") 처리 — Pong 응답 전송
			if string(msg) == "PINGPONG" {
				w.mu.Lock()
				conn.WriteMessage(websocket.TextMessage, []byte("PINGPONG"))
				w.mu.Unlock()
				continue
			}

			// KIS JSON 제어 메시지 처리 (구독 ACK, 에러 응답 등)
			if len(msg) > 0 && msg[0] == '{' {
				var ctrl struct {
					Body struct {
						RtCd  string `json:"rt_cd"`
						MsgCd string `json:"msg_cd"`
						Msg1  string `json:"msg1"`
					} `json:"body"`
				}
				if err := json.Unmarshal(msg, &ctrl); err == nil {
					if ctrl.Body.RtCd != "0" {
						log.Printf("KIS WS control error [%s]: %s — 재연결 중단, 서버를 재시작하세요", ctrl.Body.MsgCd, ctrl.Body.Msg1)
						w.mu.Lock()
						w.noReconnect = true
						w.mu.Unlock()
					} else {
						log.Printf("KIS WS control: %s", ctrl.Body.Msg1)
					}
				}
				continue
			}

			// 수신된 Raw 데이터를 파서(Worker)가 처리할 수 있도록 버퍼드 채널로 비동기 전송
			rawCount++
			preview := msg
			if len(preview) > 200 {
				preview = preview[:200]
			}
			log.Printf("[KIS RAW #%d] %d bytes (chan=%d) | %s", rawCount, len(msg), len(w.MessageChan), preview)
			select {
			case <-ctx.Done():
				return
			case w.MessageChan <- msg:
			}
		}
	}
}

// autoReconnect 지수 백오프 기반의 자동 재연결 및 기존 구독 복구 로직
func (w *WSClient) autoReconnect(ctx context.Context) {
	defer func() {
		w.mu.Lock()
		w.reconnecting = false
		w.mu.Unlock()
	}()

	backoff := 500 * time.Millisecond
	maxBackoff := 30 * time.Second

	for {
		select {
		case <-ctx.Done():
			return
		case <-time.After(backoff):
			log.Printf("Attempting KIS WS Reconnection...")

			// 1. ApprovalKey 재발급 (만료 가능성 있음)
			if err := w.GetApprovalKey(ctx); err != nil {
				log.Printf("Reconnect Approval Key Re-Fetch Error: %v", err)
				backoff *= 2
				if backoff > maxBackoff {
					backoff = maxBackoff
				}
				continue
			}

			// 2. 소켓 연결 시도
			if err := w.Connect(ctx); err != nil {
				log.Printf("Reconnect Connect Error: %v", err)
				backoff *= 2
				if backoff > maxBackoff {
					backoff = maxBackoff
				}
				continue
			}

			log.Println("KIS WS Reconnected successfully.")

			// 3. 기존에 구독 중이던 종목들 다시 Subscribe 요청
			w.subMu.RLock()
			tickers := make([]string, 0, len(w.subscribers))
			for ticker := range w.subscribers {
				tickers = append(tickers, ticker)
			}
			w.subMu.RUnlock()

			for _, ticker := range tickers {
				w.Subscribe(ctx, ticker)
			}
			return
		}
	}
}

// Subscribe 종목(ticker)에 대한 체결가/호가 실시간 수신을 KIS 서버에 요청한다.
// 단일 연결에 H0STCNT0, H0STASP0 모두 구독한다.
func (w *WSClient) Subscribe(ctx context.Context, ticker string) error {
	w.mu.Lock()
	defer w.mu.Unlock()

	if !w.connected || w.conn == nil {
		return fmt.Errorf("websocket is not connected")
	}

	for _, trId := range []string{"H0STCNT0", "H0STASP0"} {
		subMsg := map[string]interface{}{
			"header": map[string]string{
				"approval_key": w.approvalKey,
				"custtype":     "P",
				"tr_type":      "1", // 1: 등록(구독)
				"content-type": "utf-8",
			},
			"body": map[string]interface{}{
				"input": map[string]string{
					"tr_id":  trId,
					"tr_key": ticker,
				},
			},
		}
		if err := w.conn.WriteJSON(subMsg); err != nil {
			return fmt.Errorf("write subscribe err for %s (%s): %w", ticker, trId, err)
		}
	}

	w.subMu.Lock()
	w.subscribers[ticker] = struct{}{}
	w.subMu.Unlock()

	log.Printf("Subscribed to KIS WS (Tick & Orderbook) for Ticker: %s", ticker)
	return nil
}

// Close gracefully closes the websocket
func (w *WSClient) Close() {
	w.mu.Lock()
	defer w.mu.Unlock()
	w.connected = false
	if w.conn != nil {
		w.conn.WriteMessage(websocket.CloseMessage, websocket.FormatCloseMessage(websocket.CloseNormalClosure, ""))
		w.conn.Close()
		w.conn = nil
	}
}
