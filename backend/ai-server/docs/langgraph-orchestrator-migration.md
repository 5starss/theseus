# LangGraph 오케스트레이션 적용 정리

## 목적

기존 AI 자동매매 멀티 에이전트 오케스트레이션은 `orchestrate_trading()` 함수 내부에
News -> Quant -> Rebuttal -> Judge -> 주문 실행 후처리 흐름이 직렬로 직접 작성되어 있었다.

이번 작업에서는 이 실행 흐름을 `LangGraph` 기반 상태 그래프로 전환해서,
멀티 에이전트 파이프라인을 노드 단위로 분리하고 이후 확장과 추적이 쉬운 구조로 변경했다.

## 적용 범위

- 기존 퍼블릭 함수 시그니처 유지
  - `app.trading.orchestrator.orchestrate_trading()`
  - `app.trading.orchestrator.run_news_agent()`
  - `app.trading.orchestrator.run_quant_agent()`
  - `app.trading.orchestrator.run_rebuttal_agent()`
- API 엔드포인트 및 자동매매 스케줄러 호출부는 변경 없이 유지
- 내부 실행 엔진만 LangGraph 기반으로 교체

## 변경 파일

- `backend/ai-server/app/trading/langgraph_orchestrator.py`
  - LangGraph 기반 신규 오케스트레이터 추가
- `backend/ai-server/app/trading/orchestrator.py`
  - 기존 진입점을 LangGraph 오케스트레이터 재노출 형태로 단순화
- `backend/ai-server/requirements.txt`
  - `langgraph` 의존성 추가
- `backend/ai-server/tests/test_langgraph_orchestrator.py`
  - LangGraph 경유 실행 기본 테스트 추가

## 그래프 구조

초기 상태에서 아래 순서로 실행된다.

1. `load_context`
2. `news_agent`
3. `quant_agent`
4. `rebuttal_agent`
5. `judge_agent`
6. `apply_constraints`
7. `finalize_execution`

### 각 노드 역할

#### `load_context`

- 사용자 투자성향 조회
- 전략 프로필 계산
- 전략 슬롯 계산
- 계좌 스냅샷 조회
- 현재 보유수량 및 현재가 조회

#### `news_agent`

- 뉴스/커뮤니티 검색
- `NewsReporterAgent` 호출
- 에이전트 응답 상태 기록

#### `quant_agent`

- S3 피처 조회
- Quant 상태 생성
- 오전장 보조 문맥 생성
- `QuantAnalysisAgent` 호출
- 에이전트 응답 상태 기록

#### `rebuttal_agent`

- News/Quant 점수 차이 계산
- 임계치 이상이면 `RebuttalAgent` 호출

#### `judge_agent`

- 신호 확신도 계산
- 매수/매도 허용 수량 계산
- Judge 입력 payload 구성
- `JudgeAgent` 호출
- 에이전트 응답 상태 기록

#### `apply_constraints`

- 계좌 제약 조건 반영
- 계좌 스냅샷 메타데이터 추가
- `workflow=langgraph`, `workflow_version=v1` 메타데이터 추가

#### `finalize_execution`

- `execute_immediately=True` 이면 실제 주문 실행
- 아니면 `planned` 또는 `hold` 상태만 반환

## 상태 객체

LangGraph 상태는 `TradingGraphState` 로 정의했다.

주요 필드:

- 입력 필드
  - `ticker`
  - `available_cash`
  - `user_id`
  - `account_type`
  - `invest_style`
  - `execute_immediately`
  - `score_gap_threshold`
  - `strategy_slot`
- 실행 중 생성 필드
  - `strategy_profile`
  - `resolved_slot`
  - `actual_available_cash`
  - `current_holding`
  - `curr_price`
  - `news_card`
  - `quant_card`
  - `quant_state`
  - `rebuttal_result`
  - `signal_confidence`
  - `judge_payload`
  - `order_card`
  - `execution_status`

## 호환성

기존 호출부는 그대로 유지된다.

- `trade.py` 의 수동 오케스트레이션 API는 그대로 `orchestrate_trading()` 호출
- `auto_trade.py` 의 자동매매 사이클도 그대로 `orchestrate_trading()` 호출

즉 외부 인터페이스는 유지하고 내부 실행 구조만 변경했다.

## 테스트

추가된 테스트:

- `backend/ai-server/tests/test_langgraph_orchestrator.py`

검증 내용:

- LangGraph 경유로 오케스트레이션이 수행되는지
- 결과에 `workflow=langgraph` 가 포함되는지
- `execution_status` 가 기대값으로 반환되는지
- agent response 기록이 3회 호출되는지

## 현재 제약사항

현재 작업 환경에서는 아래 이유로 실제 런타임 검증이 완료되지는 않았다.

- `langgraph` 패키지가 아직 설치되지 않음
- `pip`, `pip3`, `ensurepip`, `uv` 명령을 사용할 수 없는 환경
- `pytest` 미설치로 테스트 실행 불가

즉 현재 상태는 코드 반영까지 완료된 상태이며, 실제 서버 실행을 위해서는
배포/개발 환경에서 `langgraph` 설치가 추가로 필요하다.

## 후속 작업 권장사항

1. 실행 환경에 `langgraph` 설치
2. 가상환경 또는 Docker 이미지 빌드 단계에 `requirements.txt` 반영
3. `pytest` 환경에서 `test_langgraph_orchestrator.py` 실행
4. 필요하면 다음 단계로 분기 노드 추가
   - 예: Rebuttal skip 분기
   - 예: Judge 실패 복구 분기
   - 예: Human-in-the-loop 승인 분기
