# Simulation Runners

`simulate_agent_replay.py`는 히스토리컬 뉴스 파일과 DB 1분봉을 사용해 에이전트 전략을 replay하는 1차 시뮬레이터입니다.

예시:

```bash
cd backend/ai-server
python runner/simulate_agent_replay.py \
  --tickers 005930 \
  --start-date 2025-06-20 \
  --end-date 2026-03-19 \
  --news-dir storage/news_backfill \
  --initial-cash 5000000 \
  --invest-style SHORT
```

출력:

- `decisions.jsonl`: 일자별 전략 카드
- `fills.csv`: 실제 체결 시점/가격/수량
- `daily_summary.csv`: 일자별 매수/매도 횟수와 금액 요약
- `position_timeline.csv`: 거래 후 누적 보유 수량/평단/현금 변화
- `events.jsonl`: 17:00 feature batch, 08:00 뉴스 적재, 08:05 전략 생성, 장중 replay 이벤트 로그
- `summary.json`: 실행 요약

`naver_news_backfill.py`는 네이버 뉴스 검색 API로 날짜 범위를 하루씩 돌며 뉴스 JSON/CSV와 SQLite를 함께 적재합니다.

예시:

```bash
cd backend/ai-server
python runner/naver_news_backfill.py \
  --ticker 005930 \
  --query "삼성전자 전망" \
  --start-date 2025-06-20 \
  --end-date 2026-03-19 \
  --output-dir storage/news_backfill \
  --db-path storage/news_backfill/naver_news.db
```
