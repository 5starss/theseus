# Agent API Call Guide

`backend/ai-server` 기준으로, News/Quant 에이전트 API 호출 방법을 정리합니다.

## 1. 공통

```bash
BASE_URL="http://localhost:8086"
```

헬스체크:

```bash
curl -s "$BASE_URL/health"
```

---

## 2. News Agent

### 2.1 RAG 인덱싱 (선행 권장)

```bash
curl -s -X POST "$BASE_URL/v1/rag/ingest?ticker=005930&community_limit=15&reset_collection=true"
```

### 2.2 통합 API: News 분석 카드 생성 (권장)

```bash
curl -s -X POST \
  "$BASE_URL/v1/agents/news/analyze?ticker=005930&query=삼성전자%20단기%20전망&news_k=15&community_k=2&rerank_top_n=5"
```

응답 핵심:
- `analysis_card.$schema = analysis_card_v1`
- `analysis_card.agent = news`
- `analysis_card.stance / confidence / score / top_reasons / requested_action`

---

## 3. Quant Agent

### 3.1 (선택) 공통 모델 1회 학습

```bash
curl -s -X POST \
  "$BASE_URL/v1/quant/train-global?run_fetch=false&run_feature_extract=true&model_type=ensemble"
```

### 3.2 통합 API: Quant 분석 카드 생성 (권장)

```bash
curl -s -X POST \
  "$BASE_URL/v1/agents/quant/analyze?ticker=005930&horizon_minutes=5&use_llm_interpretation=true"
```

응답 핵심:
- `analysis_card.$schema = analysis_card_v1`
- `analysis_card.agent = quant`
- `analysis_card.stance / confidence / score / top_reasons / requested_action`
- 기본 응답은 `analysis_card` 중심(토큰 절약)
- `debug=true`일 때만 `meta.quant_evidence`와 `meta.raw_result` 포함
- `meta.quant_evidence.$schema = quant_evidence_v3`
- `meta.quant_evidence.guardrails`에 LLM이 따라야 할 stance 제약과 회피 조건 포함

### 3.2.1 LLM 해석 끄기 (엔진 기반 카드만)

```bash
curl -s -X POST \
  "$BASE_URL/v1/agents/quant/analyze?ticker=005930&use_llm_interpretation=false"
```

### 3.2.2 참고: 레거시 Quant API

- `POST /v1/quant/analysis-card`
- `POST /v1/quant/adaptive-winrate`
- `POST /v1/quant/train-global`

통합 흐름에서는 `/v1/agents/quant/analyze`를 우선 사용합니다.

### 3.3 다중 종목 adaptive threshold / 승률 계산 (배치용)

```bash
curl -s -X POST \
  "$BASE_URL/v1/quant/adaptive-winrate?tickers=005930,000660&run_fetch=false&run_feature_extract=true&run_train=true&use_pretrained=true&use_panel_model=true&reuse_global_model=true&train_global_if_missing=true&model_type=ensemble&dynamic_hold=true"
```

---

## 4. 권장 호출 순서

1. `POST /v1/rag/ingest` (뉴스 데이터 인덱싱)
2. `POST /v1/quant/train-global` (공통 모델 1회 학습, 선택)
3. `POST /v1/agents/news/analyze` (뉴스 카드 생성)
4. `POST /v1/agents/quant/analyze` (퀀트 카드 생성)
5. `POST /v1/agents/rebuttal-once` 또는 `POST /v1/agents/analyze-with-rebuttal`
6. (향후) Judge Agent에 카드+반박 결과를 전달해 최종 `OrderCard` 생성

### 순서 관련 주의

- `POST /v1/agents/quant/analyze`는 내부적으로 `quant/analysis-card`를 호출하며 **단일 종목 기준 adaptive threshold/승률 계산을 수행**하고,
  `quant_evidence_v3`(guardrail 포함 근거 JSON)을 만든 뒤, 기본값(`use_llm_interpretation=true`)에서는 Quant LLM 해석까지 수행하여 `analysis_card_v1`을 반환합니다.
- Quant Agent는 이제 News 카드를 입력으로 받지 않습니다. News/Quant 결합은 Judge 단계에서만 수행합니다.
- 따라서 Judge 연계 목적이라면 보통 `agents/quant/analyze`만 호출하면 됩니다.
- `POST /v1/quant/adaptive-winrate`는 여러 종목을 한 번에 돌리는 **배치/평가용** 엔드포인트입니다.

### 3.2.3 `debug=true` 예시

```bash
curl -s -X POST \
  "$BASE_URL/v1/agents/quant/analyze?ticker=005930&horizon_minutes=5&use_llm_interpretation=true&debug=true"
```

응답 핵심 구조:
- `analysis_card`: 최종 quant 카드
- `meta.quant_evidence.summary`: 상위 요약
- `meta.quant_evidence.guardrails.allowed_stances`: 허용 stance 목록
- `meta.quant_evidence.guardrails.blocked_stances`: 금지 stance 목록
- `meta.quant_evidence.guardrails.avoid_if`: 회피 조건
- `meta.raw_result`: 내부 계산 결과

---

## 5. One-Shot Rebuttal

### 5.1 카드만 넣고 1회 반박

```bash
curl -s -X POST "$BASE_URL/v1/agents/rebuttal-once" \
  -H "Content-Type: application/json" \
  -d '{
    "news_card": {"agent":"news","score":18,"top_reasons":["실적 개선"]},
    "quant_card": {"agent":"quant","score":-4,"top_reasons":["기술적 약세"]},
    "score_gap_threshold": 15,
    "enabled": true
  }'
```

응답 핵심:
- `triggered`: 반박 실행 여부
- `rebuttal_round`: 실행 시 `1`, 미실행 시 `0`
- `rebuttal.news_rebuttal`, `rebuttal.quant_rebuttal`

### 5.2 분석+반박 오케스트레이션(권장)

```bash
curl -s -X POST \
  "$BASE_URL/v1/agents/analyze-with-rebuttal?ticker=005930&query=삼성전자%20단기%20전망&horizon_minutes=5&use_llm_interpretation=true&score_gap_threshold=15&rebuttal_enabled=true"
```

응답:
- `news`: `/v1/agents/news/analyze` 결과
- `quant`: `/v1/agents/quant/analyze` 결과
- `rebuttal`: one-shot rebuttal 결과

### 5.3 분석+반박+판정(주문결정) Full Pipeline

```bash
curl -s -X POST \
  "$BASE_URL/v1/agents/full-decision?ticker=005930&query=삼성전자%20단기%20전망&current_price=72300&available_cash=5000000&risk_type=moderate&horizon_minutes=5&use_llm_interpretation=true&score_gap_threshold=15&rebuttal_enabled=true"
```

응답:
- `analysis.news`: News 카드
- `analysis.quant`: Quant 카드
- `analysis.rebuttal`: 1회 반박 결과
- `judge.order_card`: 최종 주문 카드(가격/수량 포함)

---

## 6. 참고 엔드포인트

- `POST /v1/quant/feature-extract`: 피처 추출만 실행
- `POST /v1/quant/train`: 종목 단일 모델 학습
- `POST /v1/news/analysis-card`: 레거시 News 카드 생성 API
- `POST /v1/quant/analysis-card`: 레거시 Quant 카드 생성 API
- `POST /v1/rag/chat`: 카드가 아닌 자연어 답변
- `GET /v1/storage/status?category=quant|news`: 저장 파일 상태 확인
