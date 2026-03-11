package service

import (
	"context"
	"encoding/json"
	"log"
	"sync"
	"time"

	"market-server/internal/domain"

	"github.com/gorilla/websocket"
)

type WsAction string

const (
	ActionSubscribe   WsAction = "SUBSCRIBE"
	ActionUnsubscribe WsAction = "UNSUBSCRIBE"

	TopicHome40    = "HOME_40"
	TopicOrderbook = "ORDERBOOK"
	TopicTick      = "TICK"
)

type WsClientMessage struct {
	Action WsAction `json:"action"`
	Topic  string   `json:"topic"`
	Ticker string   `json:"ticker,omitempty"`
}

type WsClient struct {
	ID   string
	Conn *websocket.Conn
	Send chan []byte
	Hub  *WSHub
}

type WSHub struct {
	stockSvc *StockService

	clients    map[*WsClient]bool
	Register   chan *WsClient
	Unregister chan *WsClient

	// 토픽 문자열 -> 구독 중인 클라이언트 맵
	subClients map[string]map[*WsClient]bool
	mu         sync.RWMutex
}

func NewWSHub(stockSvc *StockService) *WSHub {
	return &WSHub{
		stockSvc:   stockSvc,
		clients:    make(map[*WsClient]bool),
		Register:   make(chan *WsClient),
		Unregister: make(chan *WsClient),
		subClients: make(map[string]map[*WsClient]bool),
	}
}

func (h *WSHub) Run(ctx context.Context) {
	// 백그라운드 브로드캐스터 시작
	go h.broadcaster_HOME_40(ctx)

	for {
		select {
		case client := <-h.Register:
			h.mu.Lock()
			h.clients[client] = true
			count := len(h.clients)
			h.mu.Unlock()
			log.Printf("[WSHub] 클라이언트 등록됨. 총 클라이언트 수: %d", count)

		case client := <-h.Unregister:
			h.mu.Lock()
			if _, ok := h.clients[client]; ok {
				delete(h.clients, client)
				close(client.Send)
				// 구독 정보 정리
				for topic, cMap := range h.subClients {
					if cMap[client] {
						delete(cMap, client)
						if len(cMap) == 0 {
							delete(h.subClients, topic)
						}
					}
				}
			}
			count := len(h.clients)
			h.mu.Unlock()
			log.Printf("[WSHub] 클라이언트 연결 해제됨. 총 클라이언트 수: %d", count)

		case <-ctx.Done():
			log.Println("[WSHub] Hub 종료됨")
			return
		}
	}
}

func (h *WSHub) HandleMessage(client *WsClient, msgData []byte) {
	var msg WsClientMessage
	if err := json.Unmarshal(msgData, &msg); err != nil {
		log.Printf("[WSHub] 메시지 파싱 실패: %v", err)
		return
	}

	topicKey := msg.Topic
	if msg.Topic == TopicOrderbook || msg.Topic == TopicTick {
		if msg.Ticker == "" {
			return
		}
		topicKey = msg.Topic + ":" + msg.Ticker
	}

	// 🔒 토픽별 권한 체크 (인가 검증)
	if msg.Topic == TopicOrderbook && client.ID == "" {
		log.Printf("[WSHub] 비인가 클라이언트의 호가창 구독 시도 차단 (Client %p)", client)
		// 클라이언트에게 에러 메시지 전송
		errMsg, _ := json.Marshal(map[string]interface{}{
			"topic": "ERROR",
			"data":  "호가창은 로그인이 필요한 서비스입니다.",
		})

		// 비동기 채널 전송
		select {
		case client.Send <- errMsg:
		default:
		}

		return // 구독 무시
	}

	h.mu.Lock()
	defer h.mu.Unlock()

	switch msg.Action {
	case ActionSubscribe:
		if h.subClients[topicKey] == nil {
			h.subClients[topicKey] = make(map[*WsClient]bool)
		}
		h.subClients[topicKey][client] = true
		log.Printf("[WSHub] 클라이언트가 %s 토픽을 구독함", topicKey)

	case ActionUnsubscribe:
		if h.subClients[topicKey] != nil {
			delete(h.subClients[topicKey], client)
			if len(h.subClients[topicKey]) == 0 {
				delete(h.subClients, topicKey)
			}
			log.Printf("[WSHub] 클라이언트가 %s 토픽 구독을 해지함", topicKey)
		}
	}
}

// Broadcast 특정 토픽을 구독하는 모든 클라이언트에게 단건 메시지를 전송한다.
func (h *WSHub) Broadcast(topicKey string, data []byte) {
	h.mu.RLock()
	clients, ok := h.subClients[topicKey]
	h.mu.RUnlock()

	if !ok || len(clients) == 0 {
		return // 구독자가 없으면 전송 취소
	}

	// 구독 중인 클라이언트들에게 비동기로 전송
	h.mu.RLock()
	for client := range clients {
		select {
		case client.Send <- append([]byte(nil), data...):
		default:
			// 버퍼 꽉 참 (클라이언트가 너무 느린 경우 메시지 드롭)
			log.Printf("[WSHub] %s 브로드캐스트 전송 실패 (버퍼 꽉참) - Client %p", topicKey, client)
		}
	}
	h.mu.RUnlock()
}

func (h *WSHub) broadcaster_HOME_40(ctx context.Context) {
	ticker := time.NewTicker(500 * time.Millisecond) // 0.5초 배치
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			h.mu.RLock()
			clientCount := len(h.subClients[TopicHome40])
			h.mu.RUnlock()

			if clientCount == 0 {
				continue // 구독자가 없으면 건너뜀
			}

			// 부모 ctx를 전파하여 Hub 종료 시 Redis 조회도 함께 취소
			bgCtx, cancel := context.WithTimeout(ctx, 400*time.Millisecond)
			stocks, err := h.stockSvc.GetTopStocks(bgCtx, 20, domain.RankTypeVolume)
			cancel()

			if err != nil {
				log.Printf("[WSHub] HOME_40 브로드캐스트 실패: %v", err)
				continue
			}

			payload, _ := json.Marshal(map[string]interface{}{
				"topic": TopicHome40,
				"data":  stocks,
			})

			h.mu.RLock()
			for client := range h.subClients[TopicHome40] {
				select {
				case client.Send <- payload:
				default:
				}
			}
			h.mu.RUnlock()
		}
	}
}
