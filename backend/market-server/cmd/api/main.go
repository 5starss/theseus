package main

import (
	"context"
	"database/sql"
	"fmt"
	"log"
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

	// 5. 백그라운드 랭킹 스케줄러 시작 (30초 간격, 즉시 1회 실행)
	ctx := context.Background()
	stockSvc.StartRankingScheduler(ctx, 30*time.Second)

	// 6. 라우터 설정
	r := gin.Default()

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

	// 7. 서버 실행
	if err := r.Run(":" + cfg.Server.Port); err != nil {
		log.Fatalf("서버 실행 실패: %v", err)
	}
}
