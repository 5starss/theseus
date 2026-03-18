package main

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"market-server/internal/config"
	"market-server/internal/handler"
	"market-server/internal/repository"
	"market-server/internal/service"
	"market-server/internal/worker"
	"market-server/pkg/kafka"
	kisClient "market-server/pkg/kis"
	redisClient "market-server/pkg/redis"

	"github.com/gin-gonic/gin"
	_ "github.com/go-sql-driver/mysql"
	"github.com/joho/godotenv"
)

func main() {
	// 1. .env 파일 로드 (없으면 무시 — 운영환경은 OS 환경변수 사용)
	if err := godotenv.Load(); err != nil {
		log.Println(".env 파일 없음, OS 환경변수를 사용합니다.")
	}

	// 2. 환경변수 기반 설정 로드
	cfg := config.Load()

	if len(cfg.KIS) == 0 {
		log.Fatalf("KIS API Key가 설정되지 않았습니다. .env에 KIS_APP_KEY_1, KIS_APP_SECRET_1 을 확인하세요.")
	}
	log.Printf("KIS API Key %d개 로드됨 (세션당 20종목, 최대 %d종목 커버 가능)",
		len(cfg.KIS), len(cfg.KIS)*20)

	// 3. 인프라 클라이언트 초기화
	rdb, err := redisClient.NewClient(cfg.Redis)
	if err != nil {
		log.Fatalf("Redis 연결 실패: %v", err)
	}
	defer rdb.Close()

	dsn := fmt.Sprintf("%s:%s@tcp(%s:%s)/%s",
		cfg.MySQL.User, cfg.MySQL.Password, cfg.MySQL.Host, cfg.MySQL.Port, cfg.MySQL.DBName)
	db, err := sql.Open("mysql", dsn)
	if err != nil {
		log.Fatalf("MySQL 연결 초기화 실패: %v", err)
	}
	defer db.Close()
	if err := db.Ping(); err != nil {
		log.Fatalf("MySQL Ping 실패 (DB를 실행 중인지 확인하세요): %v", err)
	}

	kafkaProducer := kafka.NewProducer(cfg.Kafka)

	// 4. KIS WS Pool 초기화 (다중 세션)
	pool := kisClient.NewWSPool(cfg.KIS)

	// 5. 취소 가능한 컨텍스트 생성 (모든 백그라운드 고루틴이 공유)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()

	if err := pool.ConnectAll(ctx); err != nil {
		log.Fatalf("KIS WSPool 연결 실패: %v", err)
	}

	// 6. MarketDataWorker 구동 (체결가/호가 → Kafka & Redis)
	dataWorker := worker.NewMarketDataWorker(pool, kafkaProducer, rdb)
	workerCount := pool.ClientCount() * 2
	if workerCount < 5 {
		workerCount = 5
	}
	dataWorker.Start(ctx, workerCount)

	// 7. 종목 구독 (세션당 20종목씩 자동 분배)
	tickers := worker.GetTargetTickers()
	pool.SubscribeAll(ctx, tickers)

	// 8. 의존성 주입 (Repository → Service → Handler)
	stockRepo := repository.NewStockRepository(rdb, db)
	stockSvc := service.NewStockService(stockRepo)

	// 8-1. KIS REST API 클라이언트 초기화 및 토큰 워커 시작 (첫 번째 키 사용)
	restKisClient := kisClient.NewClient(cfg.KIS[0])
	go restKisClient.StartTokenWorker(ctx)

	// 8-2. DailySyncWorker 구동 (비동기 과거 일봉 동기화)
	dailySyncWorker := worker.NewDailySyncWorker(restKisClient, stockRepo)
	go dailySyncWorker.SyncPastDailyCandles(ctx)
	go dailySyncWorker.StartDailyCloseScheduler(ctx) // 장 마감(15:35 KST) 후 오늘자 일봉 확정 저장

	// 8-3. CandleWorker 구동 (1분봉 생성 및 저장)
	candleConsumer := kafka.NewConsumer(cfg.Kafka, "candle-worker-group")
	candleWorker := worker.NewCandleWorker(candleConsumer, stockRepo, cfg.Kafka.TickTopic)
	candleWorker.Start(ctx)

	// 9. 라우터 설정
	r := gin.Default()

	wsHub := service.NewWSHub(stockSvc)
	go wsHub.Run(ctx)
	wsHandler := handler.NewWSHandler(wsHub)

	// Streamer 구동 (Kafka -> WSHub 단건 브로드캐스트 전송)
	kafkaConsumer := kafka.NewConsumer(cfg.Kafka, "market-streamer-group")
	streamer := worker.NewMarketDataStreamer(kafkaConsumer, wsHub, cfg.Kafka.TickTopic, cfg.Kafka.OrderbookTopic)
	streamer.Start(ctx)

	r.GET("/ping", func(c *gin.Context) {
		c.JSON(200, gin.H{"status": "UP", "server": "market-server (Go)"})
	})

	stockHandler := handler.NewStockHandler(stockSvc)
	r.GET("/api/v1/stocks", stockHandler.GetStockList)
	r.GET("/api/v1/stocks/:ticker", stockHandler.GetTickSnapshot)
	r.GET("/api/v1/stocks/:ticker/candles", stockHandler.GetCandles)
	r.GET("/api/v1/stocks/:ticker/orderbook", stockHandler.GetOrderbook)
	r.GET("/ws/v1/stocks", wsHandler.ServeWS)

	// 10. HTTP 서버 설정 및 Graceful Shutdown
	srv := &http.Server{
		Addr:    ":" + cfg.Server.Port,
		Handler: r,
	}

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	go func() {
		<-quit
		log.Println("종료 신호 수신, 서버를 graceful하게 종료합니다...")
		cancel() // 모든 백그라운드 고루틴 취소

		// HTTP 서버 종료
		shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer shutdownCancel()
		if err := srv.Shutdown(shutdownCtx); err != nil {
			log.Fatalf("서버 강제 종료: %v", err)
		}

		// WSPool 종료 (소켓 닫기 → Fan-in 종료 → 공유 채널 닫기)
		pool.Close()
		time.Sleep(100 * time.Millisecond)
		dataWorker.Wait()

		// Kafka Consumer (Streamer) 종료 대기
		streamer.Wait()
		if err := kafkaConsumer.Close(); err != nil {
			log.Printf("Streamer Kafka Consumer 종료 오류: %v", err)
		}

		// CandleWorker 종료 대기
		candleWorker.Stop()
		if err := candleConsumer.Close(); err != nil {
			log.Printf("CandleWorker Kafka Consumer 종료 오류: %v", err)
		}

		// Kafka 종료
		if err := kafkaProducer.Close(); err != nil {
			log.Printf("Kafka 종료 오류: %v", err)
		}
	}()

	log.Printf("서버 시작: :%s", cfg.Server.Port)
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		log.Fatalf("서버 실행 실패: %v", err)
	}
	log.Println("서버 종료 완료")
}
