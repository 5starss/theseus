import os
import time
import json
import logging
import re
from datetime import datetime
from typing import List, Dict, Any

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from app.schemas import Document as AppDocument

logger = logging.getLogger(__name__)

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STORAGE_DIR = os.path.join(BASE_DIR, "storage")

# 노이즈를 걸러내기 위한 토큰 (05_pjt 로직 재사용)
NOISE_TOKENS = {"주주", "팔로우", "공유하기 버튼", "더 보기"}

def is_noise(line: str) -> bool:
    s = (line or "").strip()
    if not s:
        return True
    if s in NOISE_TOKENS:
        return True
    if re.fullmatch(r"\d+", s):
        return True
    if re.search(r"(방금|초|분|시간|일)\s*(전|・)", s) or "팔로워" in s:
        return True
    if re.search(r"\d{1,2}\s*월.*\d{1,2}\s*일", s):
        return True
    if re.search(r"\d{1,2}:\d{2}", s):
        return True
    if ("상위" in s and "%" in s) or ("수익" in s and "%"):
        return True
    return False

def get_chrome_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 백그라운드 실행을 권장
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_argument("--log-level=3")  # 불필요한 로그 숨김
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    return webdriver.Chrome(options=chrome_options)

def fetch_toss_community(ticker: str, limit: int = 15, max_scroll: int = 5) -> List[Dict[str, str]]:
    """결과적으로 [{'nickname': '...', 'body': '...'}, ...] 형태의 리스트 반환"""
    driver = None
    try:
        driver = get_chrome_driver()
        wait = WebDriverWait(driver, 10)
        
        # 주식 코드를 통해 바로 다이렉트로 토스증권 커뮤니티로 진입합니다. (예: A005930)
        url = f"https://www.tossinvest.com/stocks/A{ticker}/community"
        driver.get(url)
        time.sleep(2)
        
        results = []
        seen = set()
        last_height = driver.execute_script("return document.body.scrollHeight")
        
        for _ in range(max_scroll):
            blocks = driver.find_elements(By.CSS_SELECTOR, "div[data-section-name='커뮤니티__게시글']")
            for art in blocks:
                try:
                    more_btn = art.find_element(By.XPATH, ".//button[contains(text(), '더 보기')]")
                    driver.execute_script("arguments[0].click();", more_btn)
                    time.sleep(0.1)
                except Exception:
                    pass
                
                raw = [(ln or "").strip() for ln in (art.text or "").splitlines()]
                lines = [ln for ln in raw if not is_noise(ln)]
                
                if len(lines) < 2:
                    continue
                    
                nickname = lines[0].strip()
                body_lines = [ln.strip() for ln in lines[1:] if not is_noise(ln)]
                body = " ".join(body_lines)
                
                if not nickname or not body:
                    continue
                    
                merged = f"{nickname}: {body}"
                if merged in seen:
                    continue
                    
                seen.add(merged)
                results.append({"nickname": nickname, "body": body})
                
                if len(results) >= limit:
                    break
                    
            if len(results) >= limit:
                break
                
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                break
            last_height = new_height
            
        logger.info(f"토스 커뮤니티 댓글 {len(results)}건 크롤링 완료 (종목코드: {ticker})")
        return results[:limit]
        
    except Exception as e:
        logger.error(f"토스 커뮤니티 크롤링 실패 ({ticker}): {e}")
        return []
    finally:
        if driver:
            driver.quit()

def fetch_and_store_community(ticker: str):
    """
    커뮤니티 데이터를 크롤링하고 뉴스처럼 JSON으로 저장하는 과정을 통합합니다.
    """
    logger.info(f"커뮤니티 수집 프로세스 시작: {ticker}")
    comments = fetch_toss_community(ticker)
    
    total_data = {
        "ticker": ticker,
        "collected_at": datetime.now().isoformat(),
        "sources": {
            "community": comments
        }
    }
    
    if not os.path.exists(STORAGE_DIR):
        os.makedirs(STORAGE_DIR)
        
    file_path = os.path.join(STORAGE_DIR, f"comm_{ticker}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(total_data, f, ensure_ascii=False, indent=2)
        
    logger.info(f"원본 커뮤니티 데이터 저장 완료: {file_path}")
    return file_path

def convert_community_to_documents(comm_data_path: str) -> List[AppDocument]:
    """
    JSON으로 저장된 커뮤니티 데이터를 AppDocument(가중치 0.2 적용)로 변환합니다.
    """
    with open(comm_data_path, "r", encoding="utf-8") as f:
        raw_data = json.load(f)
        
    docs = []
    ticker = raw_data.get("ticker", "UNKNOWN")
    publish_str = raw_data.get("collected_at", datetime.now().isoformat()).replace("T", " ")[:19]
    
    for idx, item in enumerate(raw_data["sources"].get("community", [])):
        nickname = item.get("nickname", "익명")
        body = item.get("body", "")
        if not body:
            continue
            
        docs.append(AppDocument(
            id=f"COMM_{ticker}_{datetime.now().strftime('%H%M%S')}_{idx}", 
            source="TOSS_COMMUNITY",
            published_at=publish_str,
            title=f"[{ticker}] 커뮤니티 여론 ({nickname})",
            body=body,
            url=f"https://www.tossinvest.com/stocks/A{ticker}/community",
            source_rank=0.2  # 커뮤니티 가중치 0.2 적용
        ))
        
    return docs
