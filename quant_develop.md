# Quant 발전 계획서

Quant 파이프라인의 목표는 단순히 더 높은 수익률을 내는 모델을 만드는 것이 아니다. 이 시스템에서 quant는 최종 매매 판단기가 아니라, LLM이 사용할 수 있는 신뢰도 높은 정량 evidence를 생성하는 모듈이어야 한다. 따라서 모든 변경은 백테스트와 추론 일관성을 통과하더라도, 최종적으로 성능 지표가 유의미하게 좋아지고, 동시에 LLM에 넘길 근거의 신뢰성과 제약 조건이 더 명확해질 때만 채택한다.

## 핵심 목표

### 역할 정의
- quant의 1차 역할은 "매수/매도 자동 결정"이 아니라 "정량 근거 생성"이다
- LLM은 quant 출력, 뉴스, 커뮤니티, 규칙 기반 정보 등을 종합해 최종 판단을 수행한다
- 따라서 quant는 점수 하나보다 신호의 신뢰도, 한계, 금지 조건, 적용 가능 레짐을 함께 제공해야 한다

### 성능 판단 기준
- 1차 지표: Sharpe Ratio
- 2차 지표: Directional Accuracy, Win Rate
- 보조 지표: Max Drawdown(MDD), 누적 수익률, 거래 수, 거래 비용 반영 후 수익률, 신뢰도 플래그 안정성

### 성공 조건
- 변경 전 대비 Sharpe Ratio가 유의미하게 개선될 것
- 거래 비용 반영 후에도 성능 개선이 유지될 것
- Max Drawdown이 동일 수준이거나 개선될 것
- 특정 일부 구간이 아닌 다수의 walk-forward 구간에서 일관된 개선이 확인될 것
- 추론 경로의 feature schema, transform, 기간 규칙이 학습 시점과 동일하게 유지될 것
- LLM이 강한 의견을 낼 수 있는 조건과 내면 안 되는 조건이 quant evidence에 명시될 것

### 실패 조건
- Sharpe는 상승하지만 거래 비용 반영 후 초과 성과가 사라지는 경우
- 일부 구간 성능만 좋아지고 전체 구간 평균 성능이 개선되지 않는 경우
- Directional Accuracy 상승에도 불구하고 손익비 악화로 총 성과가 하락하는 경우
- 신규 피처 또는 PCA 도입으로 NaN, 정렬 오류, look-ahead bias 가능성이 증가하는 경우
- quant가 불안정한 신호를 내는데도 LLM이 강한 stance를 낼 수 있도록 설계되는 경우

## 현재 구현 상태

현재 문서에 있던 핵심 아이디어 중 일부는 이미 코드에 들어가 있다. 따라서 앞으로의 계획은 "새로 넣을 기능"과 "이미 들어갔지만 검증/고도화가 필요한 기능"을 분리해서 관리해야 한다.

### 이미 구현된 항목
- 최근 기간 슬라이싱: [feature_engineer.py](/mnt/c/DEV/S14P21A503/backend/ai-server/app/quant/feature_engineer.py) 의 `recent_window_days`
- 멀티 타임프레임 피처: [feature_engineer.py](/mnt/c/DEV/S14P21A503/backend/ai-server/app/quant/feature_engineer.py) 의 `_add_mtf_features`
- Grouped PCA 기반 압축: [modeling.py](/mnt/c/DEV/S14P21A503/backend/ai-server/app/quant/modeling.py) 의 `GROUPED_PCA_GROUPS` 및 transform metadata 저장 로직
- Variant 비교 실험: [pipeline.py](/mnt/c/DEV/S14P21A503/backend/ai-server/app/quant/pipeline.py) 의 `compare_model_performance_for_ticker`, `compare_model_performance_for_universe`
- Walk-forward 기반 최적화/검증: [backtest.py](/mnt/c/DEV/S14P21A503/backend/ai-server/app/quant/backtest.py)

### 아직 불완전한 항목
- 최근 기간 슬라이싱은 들어가 있지만, 휴장일/세션 경계/거래일 기준 검증이 부족함
- MTF는 들어가 있지만 stale feature 길이, 세션 경계, 미래 참조 편향 검증 자동화가 없음
- PCA는 들어가 있지만 그룹 수가 작고 설명분산비 기반 채택 기준이 없음
- 성능 비교는 가능하지만 실험 메타데이터를 일관되게 누적 관리하는 registry가 없음
- 백테스트는 거래 비용을 반영하지만, 실제 체결 현실화 수준은 낮음
- quant evidence가 LLM 관점에서 얼마나 해석 가능하고 안전한지 평가하는 규칙이 아직 약함

## 우선순위

### 1. Quant evidence 스키마 강화
- 목표: LLM이 quant를 "숫자 하나"가 아니라 "제약이 명시된 근거"로 사용할 수 있게 만들기
- 대상: [pipeline.py](/mnt/c/DEV/S14P21A503/backend/ai-server/app/quant/pipeline.py), [agent.py](/mnt/c/DEV/S14P21A503/backend/ai-server/app/quant/agent.py)
- 작업:
- `direction`, `confidence`, `reliability_flags`, `regime_fit`, `do_not_trade_if` 같은 필드 명시
- 표본 수 부족, 노출 부족, baseline 하회 등 실패 조건을 evidence에 구조화
- quant score보다 guardrail 정보가 우선되도록 정리
- 채택 기준:
- LLM 프롬프트에서 저신뢰 신호에 강한 의견 금지 가능
- quant 신호의 사용 가능/불가 조건을 사람이 바로 해석 가능

### 2. 백테스트 현실화
- 목표: "좋아 보이는 백테스트"가 아니라 "실전 전환 가능한 백테스트"로 바꾸기
- 대상: [backtest.py](/mnt/c/DEV/S14P21A503/backend/ai-server/app/quant/backtest.py)
- 작업:
- 슬리피지 모델 추가
- 호가 스프레드 반영
- 거래량 기반 체결 cap 또는 체결 불가 조건 반영
- 장 시작/장 마감 구간 체결 정책 분리
- 채택 기준:
- 비용 반영 후에도 Sharpe 개선 유지
- trade_count가 충분히 유지될 것
- 과도한 turnover 의존 전략이 줄어들 것

### 3. 레이블 고도화
- 목표: 단순 방향 예측이 아니라 손익 구조까지 반영하는 학습 목표로 전환
- 대상: [feature_engineer.py](/mnt/c/DEV/S14P21A503/backend/ai-server/app/quant/feature_engineer.py), [modeling.py](/mnt/c/DEV/S14P21A503/backend/ai-server/app/quant/modeling.py)
- 작업:
- 현재 `target_return` 단일 레이블 외에 triple-barrier 방식 검토
- direction classification + magnitude regression 이원화 검토
- meta-labeling 도입 가능성 검토
- 채택 기준:
- Directional Accuracy뿐 아니라 PnL 기반 성과 개선
- 손익비가 나쁜 신호 필터링 개선

### 4. 피처 품질 검증 자동화
- 목표: 피처 수를 늘릴수록 누수/결측/정렬 문제를 먼저 잡는 체계 확보
- 대상: [feature_engineer.py](/mnt/c/DEV/S14P21A503/backend/ai-server/app/quant/feature_engineer.py), 테스트 코드
- 작업:
- NaN ratio 리포트 추가
- MTF merge 이후 stale length 측정
- 미래 데이터 유입 여부를 검증하는 단위 테스트 추가
- feature schema drift 체크 추가
- 채택 기준:
- 학습/추론 feature schema 불일치 0건
- leak 가능성 테스트 상시 통과

### 5. 실험 관리 체계화
- 목표: 어떤 변경이 실제 성능 개선에 기여했는지 누적 추적 가능하게 만들기
- 대상: [pipeline.py](/mnt/c/DEV/S14P21A503/backend/ai-server/app/quant/pipeline.py)
- 작업:
- `experiment_id` 도입
- 입력 데이터 기간, feature_profile, model_type, 파라미터, 결과 지표를 JSON/CSV registry로 저장
- variant 비교 결과를 한 곳에서 조회 가능하게 정리
- 채택 기준:
- 동일 조건 재현 가능
- 성능 퇴화 시 원인 역추적 가능

### 6. 종목군/레짐 분해 평가
- 목표: 평균 성능이 아니라 어떤 시장 상태에서 먹히는지 확인
- 대상: [pipeline.py](/mnt/c/DEV/S14P21A503/backend/ai-server/app/quant/pipeline.py), [backtest.py](/mnt/c/DEV/S14P21A503/backend/ai-server/app/quant/backtest.py)
- 작업:
- 종목별, 업종별, 변동성 regime별 성과 분해
- bullish/bearish/sideways 구간별 성과 비교
- recent 1y vs full-history 성과 차이 기록
- 채택 기준:
- 특정 일부 구간 편향이 아니라 다수 regime에서 일관성 확보

### 7. PCA/MTF 고도화
- 목표: 이미 넣어둔 기능을 실제 성능 기여가 있는 수준으로 다듬기
- 대상: [feature_engineer.py](/mnt/c/DEV/S14P21A503/backend/ai-server/app/quant/feature_engineer.py), [modeling.py](/mnt/c/DEV/S14P21A503/backend/ai-server/app/quant/modeling.py)
- 작업:
- PCA 그룹 확장 여부 검토
- explained variance ratio 기준으로 그룹 유지/폐기 판단
- 5m/15m/60m/1D 피처별 실효성 분리 검증
- MTF feature가 오히려 과적합을 만들면 일부만 유지
- 채택 기준:
- Baseline 대비 성능 개선이 단계별로 분리 확인될 것

## 비교 실험 프레임

### Baseline
- 기존 1분봉 단일 피처 모델

### Variant A
- 최근 기간 슬라이싱만 적용

### Variant B
- 최근 기간 슬라이싱 + MTF 피처 적용

### Variant C
- 최근 기간 슬라이싱 + MTF + Grouped PCA 적용

### Variant D
- Variant C + 체결 현실화 백테스트

### Variant E
- Variant D + 레이블 고도화

### Variant F
- Variant E + quant evidence guardrail 강화

## 채택 원칙

- 여러 변경을 한 번에 넣고 좋아졌다고 판단하지 않음
- 각 단계별 개선 폭을 기록하여 기여도가 낮거나 성능을 악화시키는 변경은 제외
- 가장 복잡한 조합이 아니라 위험 대비 성능 개선이 가장 안정적인 조합을 최종 채택안으로 선택
- 최종 채택 기준은 "백테스트 수익률"만이 아니라 "LLM이 안전하게 사용할 수 있는 evidence 품질"을 포함한다

## 검증 체크리스트

- 학습과 추론에서 feature schema가 완전히 동일한가
- MTF merge 과정에서 미래 시점 정보가 유입되지 않는가
- PCA fit 대상이 검증/추론 데이터까지 포함하지 않는가
- 신규 피처 추가 후 NaN 비율이 과도하게 증가하지 않는가
- 백테스트 개선이 거래 비용 반영 후에도 유지되는가
- 체결 현실화 후에도 성능 우위가 유지되는가
- 특정 종목/특정 시기 편향이 아닌가
- 저신뢰 quant 신호에 대해 LLM이 강한 stance를 내지 못하도록 guardrail이 작동하는가

## 결과 기록 항목

- 실험 버전명 및 적용 변경 사항
- 사용 데이터 기간
- feature_profile, model_type, label 방식
- quant evidence schema 버전
- walk-forward 평균 Sharpe Ratio
- walk-forward 구간별 Sharpe Ratio 분포
- Win Rate, Directional Accuracy, 누적 수익률, MDD
- 거래 비용 반영 전/후 성과 차이
- 체결 현실화 반영 후 성과 차이
- reliability flags 분포
- LLM 사용 금지/주의 조건
- 채택 여부 및 제외 사유

## 추천 실행 순서

1. quant evidence schema 강화
2. 피처 품질 검증 자동화 추가
3. 백테스트 체결 현실화
4. 실험 registry 도입
5. 레이블 고도화 실험
6. PCA/MTF 확장 여부 최종 판단
