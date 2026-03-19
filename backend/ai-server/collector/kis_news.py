from collector.storage import get_storage_dir

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
import requests
from app.shared.infra.redis_client import redis_client

import warnings
from cryptography.utils import CryptographyDeprecationWarning
warnings.filterwarnings("ignore", category=CryptographyDeprecationWarning)

logger = logging.getLogger(__name__)

KIS_DOMAIN = "https://openapi.koreainvestment.com:9443"
REDIS_TOKEN_KEY = "kis_access_token"

_KIS_ACCESS_TOKEN: Optional[str] = None





def get_kis_access_token() -> str:
    global _KIS_ACCESS_TOKEN
    if _KIS_ACCESS_TOKEN:
        return _KIS_ACCESS_TOKEN

    r = redis_client.get_client()
    
    # 1) Redis에서 먼저 조회
    try:
        cached_token = r.get(REDIS_TOKEN_KEY)
        if cached_token:
            _KIS_ACCESS_TOKEN = cached_token
            return cached_token
    except Exception as exc:
        logger.warning("Failed to fetch token from Redis: %s", exc)

    # 2) 신규 토큰 발급
    app_key = os.getenv("KIS_APP_KEY")
    app_secret = os.getenv("KIS_APP_SECRET")
    if not app_key or not app_secret:
        raise RuntimeError("KIS_APP_KEY/KIS_APP_SECRET is not configured")

    url = f"{KIS_DOMAIN}/oauth2/tokenP"
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "appsecret": app_secret,
    }
    response = requests.post(url, headers=headers, json=body, timeout=30)
    response.raise_for_status()
    data = response.json()
    
    _KIS_ACCESS_TOKEN = data.get("access_token", "")
    if not _KIS_ACCESS_TOKEN:
        raise RuntimeError("Failed to issue KIS access token")

    # 3) Redis에 저장 (만료 시간 설정)
    try:
        # KIS 만료 시간 보통 24시간 (86400초), 넉넉하게 23.5시간으로 설정
        expires_in = int(data.get("expires_in", 86400))
        ttl = max(60, expires_in - 1800) # 30분 마진
        r.set(REDIS_TOKEN_KEY, _KIS_ACCESS_TOKEN, ex=ttl)
        logger.info("KIS access token newly issued and cached in Redis (TTL: %d s)", ttl)
    except Exception as exc:
        logger.warning("Failed to cache token to Redis: %s", exc)

    return _KIS_ACCESS_TOKEN


def fetch_kis_news_title(ticker: str) -> List[Dict[str, Any]]:
    token = get_kis_access_token()
    app_key = os.getenv("KIS_APP_KEY")
    app_secret = os.getenv("KIS_APP_SECRET")
    if not app_key or not app_secret:
        raise RuntimeError("KIS_APP_KEY/KIS_APP_SECRET is not configured")

    url = f"{KIS_DOMAIN}/uapi/domestic-stock/v1/quotations/news-title"
    headers = {
        "content-type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": "FHKST01011800",
        "custtype": "P",
    }
    params = {
        "FID_NEWS_OFER_ENTP_CODE": "",
        "FID_COND_MRKT_CLS_CODE": "",
        "FID_INPUT_ISCD": ticker,
        "FID_TITL_CNTT": "",
        "FID_INPUT_DATE_1": "",
        "FID_INPUT_HOUR_1": "",
        "FID_RANK_SORT_CLS_CODE": "",
        "FID_INPUT_SRNO": "",
    }
    
    response = requests.get(url, headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json().get("output", [])


