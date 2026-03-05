import json
import logging
import re
import time
from html import unescape
from typing import Any, Dict, List, Optional

import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

logger = logging.getLogger(__name__)


def _json_ld_blocks(html: str) -> List[Dict[str, Any]]:
    pattern = re.compile(
        r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        re.IGNORECASE | re.DOTALL,
    )
    blocks: List[Dict[str, Any]] = []
    for raw in pattern.findall(html):
        try:
            parsed = json.loads(unescape(raw.strip()))
        except Exception:
            continue
        if isinstance(parsed, dict):
            blocks.append(parsed)
        elif isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    blocks.append(item)
    return blocks


def _extract_json_object(text: str, start_idx: int) -> Optional[Dict[str, Any]]:
    if start_idx < 0 or start_idx >= len(text) or text[start_idx] != "{":
        return None

    depth = 0
    in_string = False
    escaped = False
    for i in range(start_idx, len(text)):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                chunk = text[start_idx : i + 1]
                try:
                    return json.loads(unescape(chunk))
                except Exception:
                    return None
    return None


def _qapage_from_raw_html(html: str) -> Optional[Dict[str, Any]]:
    marker = '"@type":"QAPage"'
    idx = html.find(marker)
    if idx == -1:
        return None

    start = html.rfind("{", 0, idx)
    while start != -1:
        parsed = _extract_json_object(html, start)
        if parsed and parsed.get("@type") == "QAPage":
            return parsed
        start = html.rfind("{", 0, start)
    return None


def _comments_from_qapage(qapage: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
    main_entity = qapage.get("mainEntity", {})
    answers = main_entity.get("suggestedAnswer", [])
    if not isinstance(answers, list):
        return []

    comments: List[Dict[str, Any]] = []
    for item in answers:
        if not isinstance(item, dict):
            continue
        text = (item.get("text") or "").strip()
        nickname = item.get("author", {}).get("name", "익명")
        if not text:
            continue
        comments.append(
            {
                "nickname": nickname,
                "body": text,
                "published_at": item.get("dateCreated"),
                "url": item.get("url"),
                "upvote_count": item.get("upvoteCount"),
            }
        )
        if len(comments) >= limit:
            break
    return comments


def _extract_comments_from_html(html: str, limit: int) -> List[Dict[str, Any]]:
    json_ld = _json_ld_blocks(html)
    qapage: Optional[Dict[str, Any]] = None
    for block in json_ld:
        if block.get("@type") == "QAPage":
            qapage = block
            break

    if qapage is None:
        qapage = _qapage_from_raw_html(html)

    if qapage is None:
        return []
    return _comments_from_qapage(qapage, limit)


def _init_chrome_driver() -> webdriver.Chrome:
    options = Options()
    options.binary_location = "/usr/bin/chromium"
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1400,1200")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    )

    try:
        return webdriver.Chrome(service=Service("/usr/bin/chromedriver"), options=options)
    except Exception:
        return webdriver.Chrome(options=options)


def fetch_toss_community_comments(ticker: str, limit: int = 15) -> List[Dict[str, Any]]:
    url = f"https://www.tossinvest.com/stocks/A{ticker}/community"
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Referer": "https://www.tossinvest.com/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
    }
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()

    comments = _extract_comments_from_html(response.text, limit)
    if comments:
        return comments

    logger.warning("Static parse failed; fallback to Selenium rendering: %s", url)
    driver: Optional[webdriver.Chrome] = None
    try:
        driver = _init_chrome_driver()
        driver.get(url)
        time.sleep(2.5)
        comments = _extract_comments_from_html(driver.page_source, limit)
        if comments:
            return comments
        logger.warning("Selenium parse also failed: %s", url)
        return []
    except Exception as exc:
        logger.warning("Selenium fallback failed: %s", exc)
        return []
    finally:
        if driver:
            driver.quit()
