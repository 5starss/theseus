import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests

from collector.storage import get_storage_dir

logger = logging.getLogger(__name__)

KIS_DOMAIN = "https://openapi.koreainvestment.com:9443"
TOKEN_FILE = ".kis_token.json"

_KIS_ACCESS_TOKEN: Optional[str] = None


def _token_file_path() -> str:
    return os.path.join(get_storage_dir(), TOKEN_FILE)


def get_kis_access_token() -> str:
    global _KIS_ACCESS_TOKEN
    if _KIS_ACCESS_TOKEN:
        return _KIS_ACCESS_TOKEN

    token_file = _token_file_path()
    if os.path.exists(token_file):
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                token_data = json.load(f)
            expired_str = token_data.get("access_token_token_expired", "")
            if expired_str:
                expired_at = datetime.strptime(expired_str, "%Y-%m-%d %H:%M:%S")
                if datetime.now() < expired_at:
                    _KIS_ACCESS_TOKEN = token_data.get("access_token", "")
                    if _KIS_ACCESS_TOKEN:
                        return _KIS_ACCESS_TOKEN
        except Exception as exc:
            logger.warning("Failed to reuse cached KIS token: %s", exc)

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

    with open(token_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
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

