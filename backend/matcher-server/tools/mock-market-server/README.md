# Mock Market Data Server

매처 서버 테스트를 위한 실시간 시세 및 체결 데이터 생성용 목(Mock) 서버입니다.

## 🚀 시작하기

### 1. 의존성 설치

```bash
cd tools/mock-market-server
npm install
```

### 2. 실행

기본적으로 `localhost:9092` 카프카 브로커를 사용합니다. 환경 변수를 통해 변경 가능합니다.

```bash
# 기본 실행
node index.js

# 카프카 브로커 지정 실행
KAFKA_BROKERS=172.17.0.1:9092 node index.js
```

## 📊 발행 토픽 및 데이터

### 1. `market-data-events` (500ms 주기)

- 이미지에서 추출한 10개 종목에 대한 최우선 매수/매도 호가(`bestBid`, `bestAsk`)를 발행합니다.

### 2. `market-trade-events` (1000ms 주기)

- 10개 종목 중 랜덤하게 선정된 종목의 실제 체결 데이터(`price`, `qty`)를 발행합니다.

## 🔧 주요 설정 (index.js)

- `STOCKS`: 테스트할 종목 리스트 및 기초 가격 설정.
- `setInterval` 주기: 데이터 발행 속도 조절 가능.
