# 📈 싸피증권 (SSAFY Securities)

> 💡 **“1억으로 시작하는 AI 기반 가상 주식 투자 플랫폼”**

싸피증권은 실시간 주식 데이터와 AI 자동매매 기능을 결합한  
**가상 주식 거래 및 전략 실험 플랫폼**입니다.

사용자는 실제 시장 데이터를 기반으로 투자 경험을 쌓고,  
AI 에이전트를 통해 자동매매 전략을 실행하고 검증할 수 있습니다.

---

# 🚀 주요 기능

## 📊 실시간 주식 거래
- KIS API 기반 실시간 시세 및 호가 데이터 수신
- 종목 검색 및 상세 정보 조회
- 캔들 차트 및 거래량 분석

## 💰 가상 투자 시스템
- 1억 원 가상 자본 제공
- 주문 (매수 / 매도) 및 체결 처리
- 포지션 및 수익률 관리

## ⚙️ 매칭 엔진
- 자체 구현 주문 매칭 시스템
- 실시간 체결 처리
- 주문장 기반 거래 시뮬레이션

## 🤖 AI 자동매매
- 뉴스 + 시장 데이터 기반 전략 분석
- 자연어 기반 전략 정의 (RSI, EMA 등)
- 자동 매수/매도 실행

## 🔔 실시간 알림
- SSE 기반 이벤트 스트리밍
- 주문 체결 및 상태 알림

---

# 🏗️ 시스템 아키텍처

Client

↓

Nginx (HTTPS)

↓

API Gateway (Spring Cloud Gateway)

↓

| core-api | matcher | market | ai-server |

↓

| RDS(MySQL) | Redis | Kafka |


---

# ⚙️ 기술 스택

## 🖥 Backend
- Java 21, Spring Boot
- Spring Cloud Gateway
- JPA (Hibernate)

## 🤖 AI
- Python, FastAPI

## 📡 데이터 & 메시징
- MySQL (AWS RDS)
- Redis
- Apache Kafka

## 🌐 Infra
- Docker / Docker Compose
- Nginx (HTTPS)
- Jenkins (CI/CD)
- AWS EC2

## 📊 Monitoring
- Prometheus
- Grafana

---

# 🔄 CI/CD

- GitLab 기반 브랜치 전략 (dev → main)
- Jenkins 자동 빌드 및 배포
- Docker Compose 기반 서비스 재배포

```bash
docker-compose up -d --build api-gateway
```


📦 프로젝트 구조
```
backend/
  ├── api-gateway
  ├── core-api-server
  ├── matcher-server
  ├── market-server
  └── ai-server

docker-compose-prod/
nginx/
frontend/
```

## 🎯 서비스 목표
- 개인 투자자의 실전 투자 경험 제공
- AI 기반 자동매매 전략 실험
- 안전한 환경에서 투자 학습 가능

## 🏁 한 줄 소개

- 💡 “AI가 대신 투자하는, 실전형 주식 시뮬레이션 플랫폼”