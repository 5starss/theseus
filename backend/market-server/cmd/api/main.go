package main

import (
	"github.com/gin-gonic/gin"
)

func main() {
	// 1. 스프링의 내장 톰캣 및 ApplicationContext 초기화 역할
	r := gin.Default()

	// 2. 도커/인프라 배포 테스트용 헬스체크 엔드포인트
	r.GET("/ping", func(c *gin.Context) {
		c.JSON(200, gin.H{
			"status": "UP",
			"server": "market-server (Go)",
		})
	})

	// 3. 8085 포트로 서버 실행
	r.Run(":8085")
}