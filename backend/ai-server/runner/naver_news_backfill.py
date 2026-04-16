import argparse
import csv
import json
import random
import re
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote_plus

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

KST = timezone(timedelta(hours=9))


def parse_args():
    parser = argparse.ArgumentParser(description="네이버 뉴스 검색 결과 기반 백필 크롤러")
    parser.add_argument("--query", default="삼성전자 전망", help="검색어")
    parser.add_argument("--ticker", default="005930", help="종목 코드")
    parser.add_argument("--daily-limit", type=int, default=40, help="하루 최대 수집 건수")
    parser.add_argument("--months", type=int, default=9, help="오늘 기준 과거 N개월")
    parser.add_argument("--start-date", help="수집 시작일 (YYYY-MM-DD)")
    parser.add_argument("--end-date", help="수집 종료일 (YYYY-MM-DD)")
    parser.add_argument("--db-path", default="storage/news_backfill/naver_news.db", help="SQLite 저장 경로")
    parser.add_argument("--output-dir", default="storage/news_backfill", help="일자별 CSV/JSON 저장 경로")
    parser.add_argument("--headless", action="store_true", help="헤드리스 모드 실행")
    parser.add_argument("--min-sleep", type=float, default=1.0, help="요청 간 최소 대기")
    parser.add_argument("--max-sleep", type=float, default=2.2, help="요청 간 최대 대기")
    return parser.parse_args()


def ensure_dirs(db_path: str, output_dir: str):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_dir).mkdir(parents=True, exist_ok=True)


def create_db(db_path: str):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            keyword TEXT NOT NULL,
            title TEXT NOT NULL,
            press TEXT,
            article_url TEXT,
            naver_url TEXT,
            date_text TEXT,
            target_date TEXT NOT NULL,
            collected_at TEXT NOT NULL,
            UNIQUE(ticker, title, article_url, target_date)
        )
        """
    )
    cur.execute("PRAGMA table_info(news)")
    existing_columns = {row[1] for row in cur.fetchall()}
    required_columns = {
        "ticker": "TEXT NOT NULL DEFAULT ''",
        "keyword": "TEXT NOT NULL DEFAULT ''",
        "title": "TEXT NOT NULL DEFAULT ''",
        "press": "TEXT DEFAULT ''",
        "article_url": "TEXT DEFAULT ''",
        "naver_url": "TEXT DEFAULT ''",
        "date_text": "TEXT DEFAULT ''",
        "target_date": "TEXT NOT NULL DEFAULT ''",
        "collected_at": "TEXT NOT NULL DEFAULT ''",
    }
    for column_name, column_definition in required_columns.items():
        if column_name in existing_columns:
            continue
        cur.execute(f"ALTER TABLE news ADD COLUMN {column_name} {column_definition}")

    cur.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_news_ticker_target_date
        ON news(ticker, target_date)
        """
    )
    conn.commit()
    conn.close()


def save_rows(db_path: str, rows: List[Dict]) -> int:
    if not rows:
        return 0

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    inserted = 0
    for row in rows:
        try:
            cur.execute(
                """
                INSERT INTO news (
                    ticker, keyword, title, press, article_url, naver_url,
                    date_text, target_date, collected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["ticker"],
                    row["keyword"],
                    row["title"],
                    row["press"],
                    row["article_url"],
                    row["naver_url"],
                    row["date_text"],
                    row["target_date"],
                    row["collected_at"],
                ),
            )
            inserted += 1
        except sqlite3.IntegrityError:
            pass

    conn.commit()
    conn.close()
    return inserted


def export_rows(output_dir: str, ticker: str, target_date: str, rows: List[Dict]) -> Optional[Dict[str, str]]:
    if not rows:
        return None

    day_dir = Path(output_dir) / target_date.replace("-", "")
    day_dir.mkdir(parents=True, exist_ok=True)

    csv_path = day_dir / f"{ticker}_{target_date.replace('-', '')}.csv"
    json_path = day_dir / f"{ticker}_{target_date.replace('-', '')}.json"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "ticker",
                "keyword",
                "title",
                "press",
                "article_url",
                "naver_url",
                "date_text",
                "target_date",
                "collected_at",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    payload = {
        "ticker": ticker,
        "date": target_date,
        "query": rows[0]["keyword"],
        "count": len(rows),
        "news": rows,
    }
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"csv": str(csv_path), "json": str(json_path)}


def daterange(start_date: datetime, end_date: datetime):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def approx_months_ago(base: datetime, months: int) -> datetime:
    return base - timedelta(days=months * 30)


def build_search_url(query: str, day: datetime, start: int) -> str:
    ds = day.strftime("%Y.%m.%d")
    de = day.strftime("%Y.%m.%d")
    nso = f"so:r,p:from{day.strftime('%Y%m%d')}to{day.strftime('%Y%m%d')}"
    return (
        "https://search.naver.com/search.naver"
        f"?where=news"
        f"&query={quote_plus(query)}"
        f"&sort=1"
        f"&photo=0"
        f"&field=0"
        f"&pd=3"
        f"&ds={ds}"
        f"&de={de}"
        f"&docid="
        f"&related=0"
        f"&mynews=0"
        f"&office_type=0"
        f"&office_section_code=0"
        f"&news_office_checked="
        f"&nso={quote_plus(nso)}"
        f"&is_sug_officeid=0"
        f"&office_category=0"
        f"&service_area=0"
        f"&start={start}"
    )


def text_or_none(locator) -> Optional[str]:
    try:
        if locator.count() == 0:
            return None
        value = locator.first.inner_text(timeout=1000).strip()
        return re.sub(r"\s+", " ", value)
    except Exception:
        return None


def extract_cards(page, ticker: str, query: str, target_date: str) -> List[Dict]:
    rows: List[Dict] = []
    collected_at = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")

    card_selectors = [
        "div.sds-comps-vertical-layout.sds-comps-full-layout",
        "div.news_wrap.api_ani_send",
        "div.news_area",
        "div[class*='news_area']",
    ]

    cards = None
    for selector in card_selectors:
        try:
            locator = page.locator(selector)
            if locator.count() > 0:
                cards = locator
                break
        except Exception:
            continue

    if cards is None or cards.count() == 0:
        return rows

    seen = set()
    for index in range(cards.count()):
        card = cards.nth(index)
        title = None
        article_url = None
        naver_url = None
        press = None
        date_text = None

        title_candidates = [
            card.locator("a.news_tit"),
            card.locator("a[class*='news_tit']"),
            card.locator("a[href]").filter(has_text=""),
        ]
        for locator in title_candidates:
            try:
                if locator.count() > 0:
                    maybe_title = locator.first.get_attribute("title") or text_or_none(locator)
                    maybe_href = locator.first.get_attribute("href")
                    if maybe_title and maybe_href:
                        title = re.sub(r"\s+", " ", maybe_title).strip()
                        article_url = maybe_href
                        break
            except Exception:
                continue

        naver_candidates = [
            card.locator("a.info").filter(has_text="네이버뉴스"),
            card.locator("a.sub_txt").filter(has_text="네이버뉴스"),
        ]
        for locator in naver_candidates:
            try:
                if locator.count() > 0:
                    naver_url = locator.first.get_attribute("href")
                    break
            except Exception:
                continue

        press_candidates = [
            card.locator("a.info.press"),
            card.locator("span.info_group a.info"),
            card.locator("span[class*='info']"),
        ]
        for locator in press_candidates:
            value = text_or_none(locator)
            if value and "면" not in value and "시간" not in value and "일 전" not in value:
                press = value
                break

        date_candidates = [
            card.locator("span.info"),
            card.locator("div.info_group span"),
            card.locator("span[class*='info']"),
        ]
        date_texts: List[str] = []
        for locator in date_candidates:
            try:
                for item_index in range(min(locator.count(), 5)):
                    value = locator.nth(item_index).inner_text(timeout=500).strip()
                    if value:
                        date_texts.append(re.sub(r"\s+", " ", value))
            except Exception:
                pass

        for value in date_texts:
            if re.search(r"\d{4}\.\d{2}\.\d{2}\.", value) or "시간 전" in value or "분 전" in value or "일 전" in value:
                date_text = value
                break

        if not title or not article_url:
            continue

        dedupe_key = (title, article_url)
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        rows.append(
            {
                "ticker": ticker,
                "keyword": query,
                "title": title,
                "press": press or "",
                "article_url": article_url,
                "naver_url": naver_url or "",
                "date_text": date_text or "",
                "target_date": target_date,
                "collected_at": collected_at,
            }
        )

    return rows


def collect_one_day(page, query: str, ticker: str, day: datetime, daily_limit: int) -> List[Dict]:
    all_rows: List[Dict] = []
    target_date = day.strftime("%Y-%m-%d")
    page_start = 1

    while len(all_rows) < daily_limit:
        page.goto(build_search_url(query, day, page_start), wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_timeout(1200)
            page.mouse.wheel(0, 1600)
            page.wait_for_timeout(500)
        except Exception:
            pass

        rows = extract_cards(page, ticker, query, target_date)
        if not rows:
            break

        existing = {(row["title"], row["article_url"]) for row in all_rows}
        new_rows = [row for row in rows if (row["title"], row["article_url"]) not in existing]
        if not new_rows:
            break

        all_rows.extend(new_rows)
        if len(rows) < 10:
            break

        page_start += 10
        time.sleep(random.uniform(0.8, 1.5))

    return all_rows[:daily_limit]


def resolve_date_range(args) -> tuple[datetime, datetime]:
    today = datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0)
    if args.start_date and args.end_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=KST)
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d").replace(tzinfo=KST)
        return start_date, end_date
    start_date = approx_months_ago(today, args.months)
    return start_date, today


def main():
    args = parse_args()
    ensure_dirs(args.db_path, args.output_dir)
    create_db(args.db_path)

    start_date, end_date = resolve_date_range(args)
    total_collected = 0
    total_inserted = 0

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=args.headless)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/123.0.0.0 Safari/537.36"
            ),
            locale="ko-KR",
            timezone_id="Asia/Seoul",
            viewport={"width": 1440, "height": 2200},
        )
        page = context.new_page()

        for day in daterange(start_date, end_date):
            try:
                rows = collect_one_day(
                    page=page,
                    query=args.query,
                    ticker=args.ticker,
                    day=day,
                    daily_limit=args.daily_limit,
                )
                inserted = save_rows(args.db_path, rows)
                paths = export_rows(args.output_dir, args.ticker, day.strftime("%Y-%m-%d"), rows)

                total_collected += len(rows)
                total_inserted += inserted
                if paths:
                    print(
                        f"[{day.strftime('%Y-%m-%d')}] collected={len(rows)} inserted={inserted} json={paths['json']}"
                    )
                else:
                    print(f"[{day.strftime('%Y-%m-%d')}] collected=0 inserted=0")

                time.sleep(random.uniform(args.min_sleep, args.max_sleep))
            except PlaywrightTimeoutError:
                print(f"[{day.strftime('%Y-%m-%d')}] timeout")
                time.sleep(random.uniform(3.0, 5.0))
            except Exception as exc:
                print(f"[{day.strftime('%Y-%m-%d')}] error={exc}")
                time.sleep(random.uniform(2.0, 4.0))

        context.close()
        browser.close()

    print(f"[완료] 총 수집 건수: {total_collected}")
    print(f"[완료] DB 신규 저장 건수: {total_inserted}")
    print(f"[완료] DB 저장 경로: {args.db_path}")
    print(f"[완료] 출력 디렉터리: {args.output_dir}")


if __name__ == "__main__":
    main()
