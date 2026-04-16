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

	if len(cfg.KIS) == 0 {
		log.Fatalf("KIS API Key가 설정되지 않았습니다. .env에 KIS_APP_KEY_1, KIS_APP_SECRET_1 을 확인하세요.")
	}
	log.Printf("KIS API Key %d개 로드됨 (세션당 20종목, 최대 %d종목 커버 가능)",
		len(cfg.KIS), len(cfg.KIS)*20)

	// 3. 인프라 연결 초기화
	redisClient, err := redis.NewClient(cfg.Redis)
	if err != nil {
		log.Fatalf("Failed to initialize Redis: %v", err)
	}
	defer redisClient.Close()

	kafkaProducer := kafka.NewProducer(cfg.Kafka)

	// 4. KIS WS Pool 초기화 (다중 세션)
	pool := kis.NewWSPool(cfg.KIS)

	// 서버 구동 시그널 수신용 컨텍스트 (Graceful Shutdown)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	// 5. 모든 WS 세션 연결 (ApprovalKey 발급 + Connect + Fan-in 시작)
	if err := pool.ConnectAll(ctx); err != nil {
		log.Fatalf("Failed to connect WSPool: %v", err)
	}

	// 6. 워커 초기화 및 구동 (종목 수 증가에 따라 워커 10개로 증설)
	dataWorker := worker.NewMarketDataWorker(pool, kafkaProducer, redisClient)
	workerCount := pool.ClientCount() * 2 // 세션당 2개 워커 (예: 3세션 = 6워커, 5세션 = 10워커)
	if workerCount < 5 {
		workerCount = 5 // 최소 5개 보장
	}
	dataWorker.Start(ctx, workerCount)

	// 7. 실시간 데이터 구독 (100종목 → 세션당 20종목씩 자동 분배)
	tickers := worker.GetTargetTickers()
	pool.SubscribeAll(ctx, tickers)

	// ---------------------------------------------------------------------- //
	// Graceful Shutdown Sequence Block
	// ---------------------------------------------------------------------- //

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit

	log.Println("Shutting down server... Implementing Strict Shutdown Sequence")

	// 시스템 컨텍스트 취소
	cancel()

	// 1. WSPool 종료 (소켓 닫기 → Fan-in 채널 닫기 → 공유 채널 닫기)
	log.Println("Step 1: Closing WSPool (all WebSocket sessions)...")
	pool.Close()
	time.Sleep(100 * time.Millisecond) // 확실한 소켓 종료 위한 짧은 대기

	// 2. Drain Channel (Wait for Workers)
	log.Println("Step 2: Waiting for Workers to drain remaining messages...")
	dataWorker.Wait()

	// 3. Close Kafka Producer
	log.Println("Step 3: Closing Kafka Producer connections...")
	if err := kafkaProducer.Close(); err != nil {
		log.Printf("Kafka Close Error: %v", err)
	}

	// 4. Redis Client Close (defer로 상단에서 이미 지정되어 있음)
	log.Println("Step 4: Closing Redis Pool... Server exiting.")
}
