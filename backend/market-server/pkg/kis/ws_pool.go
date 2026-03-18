package kis

import (
	"context"
	"fmt"
	"log"
	"sync"

	"market-server/internal/config"
)

// WSPool 여러 WSClient를 관리하여 KIS 세션당 20종목 제한을 극복한다.
// 각 WSClient의 메시지를 공유 MessageChan으로 Fan-in 하여 워커가 동일하게 소비할 수 있게 한다.
type WSPool struct {
	clients     []*WSClient
	MessageChan chan []byte // 모든 WSClient의 메시지를 모아주는 Fan-in 채널
	fanInWg     sync.WaitGroup
}

const maxTickersPerSession = 20 // 41 구독 ÷ 2(체결가+호가) = 20종목/세션

// NewWSPool 주어진 KIS 설정 슬라이스로 WSPool을 생성한다.
// 각 KISConfig에 대해 별도의 WSClient를 생성하고, Fan-in 채널을 공유한다.
func NewWSPool(configs []config.KISConfig) *WSPool {
	pool := &WSPool{
		MessageChan: make(chan []byte, 5000), // 배압 제어용 버퍼드 채널
	}

	for i, cfg := range configs {
		ws := NewWSClient(cfg)
		pool.clients = append(pool.clients, ws)
		log.Printf("WSPool: WSClient #%d 생성 (AppKey: %s...)", i+1, cfg.AppKey[:8])
	}

	return pool
}

// ConnectAll 모든 WSClient에 ApprovalKey를 발급받고 WebSocket 연결을 시작한다.
// 연결 성공한 클라이언트마다 Fan-in 고루틴을 띄운다.
func (p *WSPool) ConnectAll(ctx context.Context) error {
	var connectedCount int

	for i, ws := range p.clients {
		if err := ws.GetApprovalKey(ctx); err != nil {
			log.Printf("WSPool: WSClient #%d ApprovalKey 발급 실패: %v", i+1, err)
			continue
		}

		if err := ws.Connect(ctx); err != nil {
			log.Printf("WSPool: WSClient #%d 연결 실패: %v", i+1, err)
			continue
		}

		// Fan-in: 개별 WSClient의 MessageChan → 공유 MessageChan
		p.fanInWg.Add(1)
		go p.fanIn(ctx, ws, i+1)

		connectedCount++
		log.Printf("WSPool: WSClient #%d 연결 성공", i+1)
	}

	if connectedCount == 0 {
		return fmt.Errorf("WSPool: 연결된 WSClient가 없음 (총 %d개 시도)", len(p.clients))
	}

	log.Printf("WSPool: %d/%d 세션 연결 완료 (최대 %d종목 커버 가능)",
		connectedCount, len(p.clients), connectedCount*maxTickersPerSession)

	return nil
}

// fanIn 개별 WSClient의 MessageChan에서 메시지를 읽어 WSPool의 공유 MessageChan으로 전달한다.
func (p *WSPool) fanIn(ctx context.Context, ws *WSClient, clientID int) {
	defer p.fanInWg.Done()

	var count int64
	for msg := range ws.MessageChan {
		count++
		select {
		case <-ctx.Done():
			log.Printf("WSPool: Fan-in #%d 종료 (context cancelled, %d messages forwarded)", clientID, count)
			return
		case p.MessageChan <- msg:
		}
	}
	log.Printf("WSPool: Fan-in #%d 채널 종료 (%d messages forwarded)", clientID, count)
}

// SubscribeAll 종목 리스트를 WSClient 수에 맞게 20종목씩 균등 분배하여 구독한다.
// 키 수보다 종목이 많으면 커버 가능한 만큼만 구독하고, 나머지는 로그로 경고한다.
func (p *WSPool) SubscribeAll(ctx context.Context, tickers []string) {
	maxCoverable := len(p.clients) * maxTickersPerSession

	if len(tickers) > maxCoverable {
		log.Printf("WSPool 경고: 종목 %d개 요청되었으나 %d개 세션으로 %d종목만 커버 가능 (나머지 %d종목 생략)",
			len(tickers), len(p.clients), maxCoverable, len(tickers)-maxCoverable)
		tickers = tickers[:maxCoverable]
	}

	for i, ws := range p.clients {
		start := i * maxTickersPerSession
		if start >= len(tickers) {
			log.Printf("WSPool: WSClient #%d — 할당할 종목 없음 (이미 모든 종목 배분 완료)", i+1)
			break
		}

		end := start + maxTickersPerSession
		if end > len(tickers) {
			end = len(tickers)
		}

		assigned := tickers[start:end]
		for _, ticker := range assigned {
			if err := ws.Subscribe(ctx, ticker); err != nil {
				log.Printf("WSPool: WSClient #%d 종목 %s 구독 실패: %v", i+1, ticker, err)
			}
		}

		log.Printf("WSPool: WSClient #%d — %d종목 구독 완료 (%s ~ %s)",
			i+1, len(assigned), assigned[0], assigned[len(assigned)-1])
	}

	log.Printf("WSPool: 전체 구독 완료 — %d종목 / %d세션", len(tickers), len(p.clients))
}

// Close 모든 WSClient를 종료하고 Fan-in 고루틴이 완료되면 공유 채널을 닫는다.
func (p *WSPool) Close() {
	// 1. 모든 WSClient 소켓 종료
	for i, ws := range p.clients {
		ws.Close()
		log.Printf("WSPool: WSClient #%d 소켓 닫힘", i+1)
	}

	// 2. 각 WSClient의 MessageChan 닫기 → Fan-in 고루틴 종료 유도
	for _, ws := range p.clients {
		close(ws.MessageChan)
	}

	// 3. Fan-in 고루틴 완료 대기 후 공유 채널 닫기
	p.fanInWg.Wait()
	close(p.MessageChan)
	log.Println("WSPool: 공유 MessageChan 닫힘 — 모든 Fan-in 완료")
}

// ClientCount 현재 풀에 등록된 WSClient 수를 반환한다.
func (p *WSPool) ClientCount() int {
	return len(p.clients)
}
