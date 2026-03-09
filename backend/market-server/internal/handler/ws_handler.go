package handler

import (
	"log"
	"net/http"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/gorilla/websocket"
	"market-server/internal/service"
)

const (
	writeWait      = 10 * time.Second
	pongWait       = 60 * time.Second
	pingPeriod     = (pongWait * 9) / 10
	maxMessageSize = 512
)

var upgrader = websocket.Upgrader{
	ReadBufferSize:  1024,
	WriteBufferSize: 1024,
	CheckOrigin: func(r *http.Request) bool {
		return true // 직접 연결을 위해 모든 Origin 허용
	},
}

type WSHandler struct {
	hub *service.WSHub
}

func NewWSHandler(hub *service.WSHub) *WSHandler {
	return &WSHandler{
		hub: hub,
	}
}

// ServeWS는 GET /v1/stocks/ws 요청을 처리합니다
func (h *WSHandler) ServeWS(c *gin.Context) {
	conn, err := upgrader.Upgrade(c.Writer, c.Request, nil)
	if err != nil {
		log.Printf("[WSHandler] 업그레이드 오류: %v", err)
		return
	}

	// API Gateway에서 JWT 검증 후 주입한 헤더 읽기
	userId := c.GetHeader("X-USER-ID")

	client := &service.WsClient{
		ID:   userId, // 비회원일 경우 "", 회원이면 JWT에서 추출한 userId
		Conn: conn,
		Send: make(chan []byte, 256),
		Hub:  h.hub,
	}

	client.Hub.Register <- client

	// 새로운 고루틴에서 모든 작업을 수행하여 호출자의 메모리 참조 수집을 허용합니다.
	go writePump(client)
	go readPump(client)
}

func readPump(client *service.WsClient) {
	defer func() {
		client.Hub.Unregister <- client
		client.Conn.Close()
	}()

	client.Conn.SetReadLimit(maxMessageSize)
	client.Conn.SetReadDeadline(time.Now().Add(pongWait))
	client.Conn.SetPongHandler(func(string) error {
		client.Conn.SetReadDeadline(time.Now().Add(pongWait))
		return nil
	})

	for {
		_, message, err := client.Conn.ReadMessage()
		if err != nil {
			if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				log.Printf("[WSHandler] 예기치 않은 종료 오류: %v", err)
			}
			break
		}
		
		// 메시지를 처리를 위해 Hub로 전달
		client.Hub.HandleMessage(client, message)
	}
}

func writePump(client *service.WsClient) {
	ticker := time.NewTicker(pingPeriod)
	defer func() {
		ticker.Stop()
		client.Conn.Close()
	}()

	for {
		select {
		case message, ok := <-client.Send:
			client.Conn.SetWriteDeadline(time.Now().Add(writeWait))
			if !ok {
				// Hub에서 채널을 닫았습니다.
				client.Conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}

			w, err := client.Conn.NextWriter(websocket.TextMessage)
			if err != nil {
				return
			}
			w.Write(message)

			// 대기 중인 메시지를 현재 WebSocket 메시지에 추가합니다.
			n := len(client.Send)
			for i := 0; i < n; i++ {
				w.Write([]byte{'\n'})
				w.Write(<-client.Send)
			}

			if err := w.Close(); err != nil {
				return
			}
		case <-ticker.C:
			client.Conn.SetWriteDeadline(time.Now().Add(writeWait))
			if err := client.Conn.WriteMessage(websocket.PingMessage, nil); err != nil {
				return
			}
		}
	}
}
