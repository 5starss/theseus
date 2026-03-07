# Plan: `news_agent` 코드 최소 수정 이식

## 목표
- 기존 `backend/ai-server/news_agent` 코드를 현재 폴더 구조에 **최소 변경**으로 이식한다.
- 검색 정확도 개선(고도화)은 이식 완료 후 별도 단계로 분리한다.

## 원칙 (Minimal Change)
1. 비즈니스 로직은 건드리지 않는다.
2. 경로/임포트/실행 진입점만 조정한다.
3. 신규 기능 추가(`query_processor`, `deduplication` 등)는 이식 범위에서 제외한다.
4. 동작 확인은 `fetch -> index -> chat` 기본 플로우만 검증한다.

---

## 현재 기준점 (As-Is)
- 실행 진입점: `backend/ai-server/news_agent/main.py`
- 주요 패키지: `backend/ai-server/news_agent/app/*`
- 상대경로 의존:
  - `main.py` -> `storage`
  - `app/rag/vector_db.py` -> `./chroma_db`
- 주요 함수명:
  - `NewsVectorDB.hybrid_query()`
  - `NewsVectorDB._prepare_bm25()`

---

## 이식 범위 (In-Scope)
1. 디렉터리 배치 정리
2. import 경로 정합성 확보
3. 런타임 상대경로 안정화
4. 최소 스모크 테스트

## 제외 범위 (Out-of-Scope)
- 검색 품질 고도화(가중치 튜닝, 고급 중복 제거, 감정 점수화)
- 스키마 확장(`Document` 신규 필드 다수 추가)
- 컬렉션 샤딩/모니터링/벤치마크 신규 모듈

---

## 구현 단계

### Phase 1. 구조 고정 (필수)
1. `news_agent` 루트를 실행 기준 디렉터리로 고정한다.
2. `app` 패키지 구조를 유지한다.
3. `main.py` 경로 기준으로 `storage`, `chroma_db`가 기대 위치에 있도록 맞춘다.

완료 기준:
- `python main.py --help` 정상 동작
- import 에러 없음

### Phase 2. 경로/임포트 최소 수정 (필수)
1. `from app...` 임포트가 깨지면 아래 중 하나만 선택:
   - 실행 시 `PYTHONPATH` 설정
   - 또는 소수 파일에서 절대/상대 임포트만 최소 교정
2. 경로 하드코딩은 추가하지 않는다.
3. 함수명은 현재 코드 기준(`hybrid_query`, `_prepare_bm25`)을 유지한다.

완료 기준:
- `fetch`, `index`, `chat` 모드 진입 가능
- 경로 관련 예외 없음

### Phase 3. 최소 검증 (필수)
1. `fetch` 모드: 저장 파일 생성 확인
2. `index` 모드: Chroma 색인 완료 확인
3. `chat` 모드: 질문 1건 응답 확인

완료 기준:
- 기본 E2E 1회 성공
- 치명적 오류(ImportError, FileNotFoundError, DB 초기화 실패) 없음

### Phase 4. 개선 백로그 분리 (선택)
이식 이후 별도 브랜치에서 수행:
1. 한글 쿼리 전처리
2. BM25 튜닝
3. 하이브리드 재랭킹/중복 제거
4. 평가 자동화

---

## 파일별 작업 지침

### 우선 확인 파일
- `backend/ai-server/news_agent/main.py`
- `backend/ai-server/news_agent/app/rag/vector_db.py`
- `backend/ai-server/news_agent/app/rag/embedder.py`
- `backend/ai-server/news_agent/app/schemas.py`

### 수정 우선순위
1. 실행 깨짐 방지(import/path)
2. 데이터 입출력 경로
3. 로깅/옵션 정리

### 금지 사항
- 이식 단계에서 대규모 리팩터링 금지
- 검색 랭킹 로직 변경 금지
- 스키마 선확장 금지

---

## 체크리스트
- [ ] `planner.md` 기준으로 범위 합의 완료
- [ ] 실행 루트/환경변수 정리 완료
- [ ] import/path 최소 수정 완료
- [ ] `fetch -> index -> chat` 스모크 테스트 통과
- [ ] 개선 항목은 별도 TODO로 분리

---

## 리스크 및 대응
1. 상대경로 의존으로 실행 위치마다 실패 가능
- 대응: 실행 루트를 고정하고 문서화

2. 외부 키/환경변수 누락(`UPSTAGE_API_KEY`)
- 대응: `.env` 체크 및 시작 시 명확한 오류 로그 유지

3. 성능 개선 요구와 이식 요구가 혼합될 위험
- 대응: 이식 완료 전 기능 고도화 작업 금지

---

## 최종 산출물
1. 최소 수정 이식된 실행 가능한 코드
2. 실행/배포 시 필요한 경로·환경 문서
3. 성능 개선 백로그(후속 작업 목록)

