package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"
	"time"

	"market-server/internal/config"
	"market-server/internal/worker"
	"market-server/pkg/kafka"
	"market-server/pkg/kis"
	"market-server/pkg/redis"

	"github.com/joho/godotenv"
)

func main() {
	log.Println("Starting Market Server (Phase 2 Data Pipeline)...")

	// 1. .env 파일 로드 (없으면 무시 — 운영환경은 OS 환경변수 사용)
	if err := godotenv.Load(); err != nil {
		log.Println(".env 파일 없음, OS 환경변수를 사용합니다.")
	}

	// 2. 설정 로드
	cfg := config.Load()

	// 2. 인프라 연결 초기화
	redisClient, err := redis.NewClient(cfg.Redis)
	if err != nil {
		log.Fatalf("Failed to initialize Redis: %v", err)
	}
	defer redisClient.Close()

	kafkaProducer := kafka.NewProducer(cfg.Kafka)

	// 3. KIS 클라이언트 (REST 및 WS) 초기화
	// kisClient := kis.NewClient(cfg.KIS) // REST 필요시 사용 (현재 토큰 처리용)

	wsClient := kis.NewWSClient(cfg.KIS)

	// 서버 구동 시그널 수신용 컨텍스트 (Graceful Shutdown)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// 4. OpenAPI WS Approval Key 발급
	if err := wsClient.GetApprovalKey(ctx); err != nil {
		log.Fatalf("Failed to get KIS WS Approval Key: %v", err)
	}

	// 5. WS 연결 시작
	if err := wsClient.Connect(ctx); err != nil {
		log.Fatalf("Failed to connect to KIS WS: %v", err)
	}

	// 6. 워커 초기화 및 구동 (고루틴 5개 띄움)
	dataWorker := worker.NewMarketDataWorker(wsClient, kafkaProducer, redisClient)
	dataWorker.Start(ctx, 5)

	// 7. 실시간 데이터 구독 (Top 40 종목 동적 할당)
	tickers := worker.GetTop40Tickers()
	for _, t := range tickers {
		if err := wsClient.Subscribe(ctx, t); err != nil {
			log.Printf("Failed to subscribe %s: %v", t, err)
		}
	}

	// ---------------------------------------------------------------------- //
	// Graceful Shutdown Sequence Block
	// ---------------------------------------------------------------------- //

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down server... Implementing Strict Shutdown Sequence")

	// 시스템 컨텍스트 취소
	cancel()

	// 1. Disconnect KIS WS (수신 루프 정지)
	log.Println("Step 1: Closing KIS WebSocket Connection...")
	wsClient.Close()
	time.Sleep(100 * time.Millisecond) // 확실한 소켓 종료 위한 짧은 대기

	// 2. Close MessageChan (수신 데이터 없음 알림)
	log.Println("Step 2: Closing Message Channel...")
	close(wsClient.MessageChan)

	// 3. Drain Channel (Wait for Workers)
	log.Println("Step 3: Waiting for Workers to drain remaining messages...")
	dataWorker.Wait()

	// 4. Close Kafka Producer
	log.Println("Step 4: Closing Kafka Producer connections...")
	if err := kafkaProducer.Close(); err != nil {
		log.Printf("Kafka Close Error: %v", err)
	}

	// 5. Redis Client Close (defer로 상단에서 이미 지정되어 있음)
	log.Println("Step 5: Closing Redis Pool... Server exiting.")
}
