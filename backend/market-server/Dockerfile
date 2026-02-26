# 1단계: 빌드 환경 (Go 1.26.0)
FROM golang:1.26.0-alpine AS builder
WORKDIR /app

# 의존성 파일 복사 및 다운로드
COPY go.mod go.sum ./
RUN go mod download

# cmd/api/main.go 등 프로젝트의 모든 코드를 복사해옵니다.
COPY . .

# 빌드 타겟 경로를 cmd/api/main.go 로 지정합니다.
RUN CGO_ENABLED=0 GOOS=linux go build -o market-server ./cmd/api/main.go

# 2단계: 실행 환경 (초경량 Alpine Linux)
FROM alpine:latest
WORKDIR /app

# 타임존 설정 (한국 시간)
RUN apk add --no-cache tzdata && \
    cp /usr/share/zoneinfo/Asia/Seoul /etc/localtime && \
    echo "Asia/Seoul" > /etc/timezone

# 빌드된 Go 실행 파일만 복사
COPY --from=builder /app/market-server .

# Go 서버가 사용할 포트
EXPOSE 8085

# 컨테이너 실행
ENTRYPOINT ["./market-server"]