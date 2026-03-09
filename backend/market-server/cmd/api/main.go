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

    "github.com/gin-gonic/gin"
    _ "github.com/go-sql-driver/mysql"
    "github.com/joho/godotenv"
    "market-server/internal/config"
    "market-server/internal/handler"
    "market-server/internal/repository"
    "market-server/internal/service"
    kisClient "market-server/pkg/kis"
    redisClient "market-server/pkg/redis"
)

func main() {
    // 1. .env 파일 로드 (없으면 무시 — 운영환경은 OS 환경변수 사용)
    if err := godotenv.Load(); err != nil {
       log.Println(".env 파일 없음, OS 환경변수를 사용합니다.")
    }

    // 2. 환경변수 기반 설정 로드
    cfg := config.Load()

    // 클라우드 환경(AWS, Docker 등)에서 주입하는 PORT 최우선 적용
    port := os.Getenv("PORT")
    if port == "" {
        port = cfg.Server.Port // config 구조체에 있는 값
        if port == "" {
            port = "8085" // 최후의 기본 포트
        }
    }

    // 3. 인프라 클라이언트 초기화
    rdb, err := redisClient.NewClient(cfg.Redis)
    if err != nil {
       log.Fatalf("Redis 연결 실패: %v", err)
    }

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

    // 4. 의존성 주입 (Repository → Service → Handler)
    kisC := kisClient.NewClient(cfg.KIS)
    stockRepo := repository.NewStockRepository(rdb, db)
    stockSvc := service.NewStockService(stockRepo, kisC)

    // 5. 취소 가능한 컨텍스트 생성 (모든 백그라운드 고루틴이 공유)
    ctx, cancel := context.WithCancel(context.Background())
    defer cancel()

    // 백그라운드 랭킹 스케줄러 시작 (30초 간격, 즉시 1회 실행)
    stockSvc.StartRankingScheduler(ctx, 30*time.Second)

    // 6. 라우터 설정
    r := gin.Default()

    // WebSocket Hub 초기화 및 실행
    wsHub := service.NewWSHub(stockSvc)
    go wsHub.Run(ctx)
    wsHandler := handler.NewWSHandler(wsHub)

    // 헬스체크
    r.GET("/ping", func(c *gin.Context) {
       c.JSON(200, gin.H{
          "status": "UP",
          "server": "market-server (Go)",
       })
    })

    // 종목 리스트 조회
    stockHandler := handler.NewStockHandler(stockSvc)
    r.GET("/api/v1/stocks", stockHandler.GetStockList)
    r.GET("/api/v1/stocks/:ticker/candles", stockHandler.GetCandles)
    r.GET("/api/v1/stocks/:ticker/orderbook", stockHandler.GetOrderbook)

    // WebSocket (Direct Connection)
    r.GET("/v1/stocks/ws", wsHandler.ServeWS)

    // 7. HTTP 서버 설정
    srv := &http.Server{
       Addr:    ":" + port, // 수정된 변수 사용
       Handler: r,
    }

    // HTTP 서버 실행을 논블로킹(백그라운드)으로 넘깁니다.
    go func() {
       log.Printf("서버 시작: :%s", port)
       if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
          log.Fatalf("서버 실행 실패: %v", err)
       }
    }()

    // 메인 쓰레드는 OS 종료 신호(SIGINT, SIGTERM)가 올 때까지 여기서 대기
    quit := make(chan os.Signal, 1)
    signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
    <-quit // 신호가 들어올 때까지 블로킹

    log.Println("종료 신호 수신, 서버를 graceful하게 종료합니다...")

    // 1단계: 백그라운드 작업(랭킹 스케줄러, WebSocket 허브 등) 컨텍스트 취소
    cancel()

    // 2단계: HTTP 서버에 들어온 기존 요청들이 완료될 때까지 최대 10초 대기
    shutdownCtx, shutdownCancel := context.WithTimeout(context.Background(), 10*time.Second)
    defer shutdownCancel()

    if err := srv.Shutdown(shutdownCtx); err != nil {
       log.Fatalf("서버 강제 종료: %v", err)
    }

    log.Println("서버 종료 완료")
}