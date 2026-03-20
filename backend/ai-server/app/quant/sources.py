"""
quant/sources.py
────────────────
주식 시계열(OHLCV) 데이터의 로드·정규화·저장·검색을 담당하는 유틸리티.

주요 기능:
  - MySQL DB (candle_1m 테이블) → 표준 OHLCV DataFrame 로드 (SSH 터널 지원)
  - CSV 원본 → 표준 OHLCV DataFrame 정규화 (Fallback)
  - 정규화 데이터를 gzip JSON 으로 storage/quant 에 저장
  - storage/quant 에서 최신 파일(raw, feat, model 등) 검색
  - 저장된 JSON/GZ 데이터를 DataFrame 으로 재로드
"""

import glob
import gzip
import json
import logging
import os
import re
from datetime import datetime
from typing import List, Optional

import pandas as pd

try:
    import pymysql
    import pymysql.cursors
    _PYMYSQL_AVAILABLE = True
except ImportError:
    _PYMYSQL_AVAILABLE = False

try:
    from sshtunnel import SSHTunnelForwarder
    _SSHTUNNEL_AVAILABLE = True
except ImportError:
    _SSHTUNNEL_AVAILABLE = False

from collector.storage import get_storage_dir

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────
REQUIRED_COLUMNS = ["ts", "open", "high", "low", "close", "volume"]
_QUANT_CATEGORY = "quant"


# ──────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────
def _get_db_config() -> tuple[str, int, str, str, str]:
    host = os.getenv("DB_HOST") or os.getenv("MYSQL_HOST") or "mysql"
    port = int(os.getenv("DB_PORT") or os.getenv("MYSQL_PORT") or "3306")
    user = os.getenv("DB_USER") or os.getenv("MYSQL_USER") or "root"
    password = os.getenv("DB_PASSWORD") or os.getenv("MYSQL_PASSWORD") or ""
    database = os.getenv("DB_DATABASE") or os.getenv("MYSQL_DATABASE") or "stock_db"
    return host, port, user, password, database


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """CSV/JSON 데이터를 표준 OHLCV 포맷으로 정규화합니다."""
    renamed = {col: col.strip().lower().replace("\ufeff", "") for col in df.columns}
    df = df.rename(columns=renamed)

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")

    out = df[REQUIRED_COLUMNS].copy()
    out["ts"] = pd.to_datetime(out["ts"], errors="coerce")
    out = (
        out.dropna(subset=["ts"])
        .sort_values("ts")
        .drop_duplicates(subset=["ts"], keep="last")
    )

    for col in ["open", "high", "low", "close", "volume"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")
    out = out.dropna()

    return out.reset_index(drop=True)


def _find_latest_path(
    ticker: str,
    prefix: str,
    extensions: List[str],
    regex_pattern: Optional[str] = None,
) -> str:
    """storage/quant 내에서 지정된 접두사·확장자를 가진 최신 파일을 찾습니다."""
    storage_dir = get_storage_dir(_QUANT_CATEGORY)
    files = []
    for ext in extensions:
        pattern = os.path.join(storage_dir, f"{prefix}_{ticker}_*{ext}")
        files.extend(glob.glob(pattern))

    files = sorted(files)
    if regex_pattern:
        r = re.compile(regex_pattern)
        files = [f for f in files if r.match(os.path.basename(f))]

    if not files:
        raise FileNotFoundError(
            f"[{ticker}] '{prefix}' 데이터를 storage/quant 에서 찾을 수 없습니다."
        )
    return files[-1]


def load_json_compressed(path: str) -> dict:
    """Gzip 압축 여부를 자동으로 판단하여 JSON 데이터를 로드합니다."""
    if path.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ──────────────────────────────────────────────
# DB → DataFrame  (MySQL candle_1m)
# ──────────────────────────────────────────────
def load_ohlcv_from_db(ticker: str, days: int = 730) -> pd.DataFrame:
    """MySQL candle_1m 테이블에서 OHLCV 데이터를 로드합니다. (SSH 터널링 지원)"""
    if not _PYMYSQL_AVAILABLE:
        raise RuntimeError("pymysql 패키지가 설치되어 있지 않습니다.")

    host, port, user, password, database = _get_db_config()

    use_ssh = os.getenv("USE_SSH", "false").lower() == "true"
    
    def _fetch_data(conn_params):
        conn = pymysql.connect(**conn_params)
        try:
            with conn.cursor() as cursor:
                # days가 0이면 오늘(자정) 이후의 데이터만 가져옵니다.
                if days == 0:
                    query = """
                        SELECT
                            candle_time AS ts,
                            open_price  AS open,
                            high_price  AS high,
                            low_price   AS low,
                            close_price AS close,
                            volume
                        FROM candle_1m
                        WHERE ticker = %s
                          AND candle_time >= CURDATE()
                        ORDER BY candle_time ASC
                    """
                    cursor.execute(query, (ticker,))
                else:
                    query = """
                        SELECT
                            candle_time AS ts,
                            open_price  AS open,
                            high_price  AS high,
                            low_price   AS low,
                            close_price AS close,
                            volume
                        FROM candle_1m
                        WHERE ticker = %s
                          AND candle_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
                        ORDER BY candle_time ASC
                    """
                    cursor.execute(query, (ticker, days))
                return cursor.fetchall()
        finally:
            conn.close()

    rows = []
    if use_ssh:
        if not _SSHTUNNEL_AVAILABLE:
            raise RuntimeError("SSH 터널링을 위해 'sshtunnel' 패키지가 필요합니다.")
        
        ssh_host = os.getenv("SSH_HOST")
        ssh_port = int(os.getenv("SSH_PORT", "22"))
        ssh_user = os.getenv("SSH_USER")
        ssh_password = os.getenv("SSH_PASSWORD")
        ssh_key_path = os.getenv("SSH_KEY_PATH")

        logger.info("[%s] SSH 터널링 DB 접속 시도 (%s:%d)", ticker, ssh_host, ssh_port)
        
        tunnel_kwargs = {
            "ssh_address_or_host": (ssh_host, ssh_port),
            "ssh_username": ssh_user,
            "remote_bind_address": (host, port),
        }
        if ssh_key_path:
            tunnel_kwargs["ssh_pkey"] = ssh_key_path
        elif ssh_password:
            tunnel_kwargs["ssh_password"] = ssh_password

        with SSHTunnelForwarder(**tunnel_kwargs) as tunnel:
            conn_params = {
                "host": "127.0.0.1",
                "port": tunnel.local_bind_port,
                "user": user,
                "password": password,
                "database": database,
                "cursorclass": pymysql.cursors.DictCursor,
                "charset": "utf8mb4",
            }
            rows = _fetch_data(conn_params)
    else:
        logger.info("[%s] 직접 DB 접속 시도 (%s:%d)", ticker, host, port)
        conn_params = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
            "cursorclass": pymysql.cursors.DictCursor,
            "charset": "utf8mb4",
        }
        rows = _fetch_data(conn_params)

    if not rows:
        raise ValueError(f"[{ticker}] DB에서 데이터가 조회되지 않았습니다.")

    df = pd.DataFrame(rows)
    df = _normalize_ohlcv(df)
    logger.info("[%s] DB 로드 완료: %d건", ticker, len(df))
    return df


def get_all_tickers_from_db() -> List[str]:
    """MySQL candle_1m 테이블에 존재하는 모든 고유 ticker를 조회합니다."""
    if not _PYMYSQL_AVAILABLE:
        raise RuntimeError("pymysql 패키지가 설치되어 있지 않습니다.")

    host, port, user, password, database = _get_db_config()

    use_ssh = os.getenv("USE_SSH", "false").lower() == "true"
    
    def _fetch_tickers(conn_params):
        conn = pymysql.connect(**conn_params)
        try:
            with conn.cursor() as cursor:
                query = "SELECT DISTINCT ticker FROM candle_1m"
                cursor.execute(query)
                rows = cursor.fetchall()
                if not rows:
                    return []
                # 리스트 또는 딕셔너리로 넘어오는 결과 파싱
                return sorted([r["ticker"] if isinstance(r, dict) else r[0] for r in rows])
        finally:
            conn.close()

    tickers = []
    if use_ssh:
        if not _SSHTUNNEL_AVAILABLE:
            raise RuntimeError("SSH 터널링을 위해 'sshtunnel' 패키지가 필요합니다.")
        
        ssh_host = os.getenv("SSH_HOST")
        ssh_port = int(os.getenv("SSH_PORT", "22"))
        ssh_user = os.getenv("SSH_USER")
        ssh_password = os.getenv("SSH_PASSWORD")
        ssh_key_path = os.getenv("SSH_KEY_PATH")

        tunnel_kwargs = {
            "ssh_address_or_host": (ssh_host, ssh_port),
            "ssh_username": ssh_user,
            "remote_bind_address": (host, port),
        }
        if ssh_key_path:
            tunnel_kwargs["ssh_pkey"] = ssh_key_path
        elif ssh_password:
            tunnel_kwargs["ssh_password"] = ssh_password

        with SSHTunnelForwarder(**tunnel_kwargs) as tunnel:
            conn_params = {
                "host": "127.0.0.1",
                "port": tunnel.local_bind_port,
                "user": user,
                "password": password,
                "database": database,
                "cursorclass": pymysql.cursors.DictCursor,
                "charset": "utf8mb4",
            }
            tickers = _fetch_tickers(conn_params)
    else:
        conn_params = {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
            "cursorclass": pymysql.cursors.DictCursor,
            "charset": "utf8mb4",
        }
        tickers = _fetch_tickers(conn_params)

    return tickers


# ──────────────────────────────────────────────
# CSV → DataFrame
# ──────────────────────────────────────────────
def get_csv_path(ticker: str, data_dir: str = "data_cybos") -> str:
    path = os.path.join(data_dir, f"{ticker}_1m_2y.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {path}")
    return path


def load_ohlcv_from_csv(ticker: str, data_dir: str = "data_cybos") -> pd.DataFrame:
    csv_path = get_csv_path(ticker, data_dir)
    logger.info("CSV 로드 시작: %s", csv_path)
    raw = pd.read_csv(csv_path, encoding="utf-8-sig")
    df = _normalize_ohlcv(raw)
    return df


def fetch_and_store_timeseries(ticker: str, data_dir: str = "data_cybos") -> str:
    df = load_ohlcv_from_csv(ticker, data_dir)
    storage_dir = get_storage_dir(_QUANT_CATEGORY)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(storage_dir, f"raw_{ticker}_{stamp}.json.gz")

    payload = {
        "ticker": ticker,
        "rows": len(df),
        "generated_at": datetime.now().isoformat(),
        "data": [
            {
                "ts": row.ts.isoformat(),
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": float(row.volume),
            }
            for row in df.itertuples(index=False)
        ],
    }
    with gzip.open(out_path, "wt", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    return out_path


def get_latest_raw_path(ticker: str) -> str:
    return _find_latest_path(ticker, "raw", [".json", ".json.gz"])


def get_latest_feature_path(ticker: str) -> str:
    return _find_latest_path(ticker, "feat", [".csv", ".csv.gz"])


def get_latest_model_path(ticker: str) -> str:
    regex = rf"^model_{re.escape(ticker)}_\d{{8}}_\d{{6}}\.json$"
    return _find_latest_path(ticker, "model", [".json"], regex_pattern=regex)


def get_latest_global_model_path() -> str:
    storage_dir = get_storage_dir(_QUANT_CATEGORY)
    pattern = os.path.join(storage_dir, "model_global_*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError("global model 데이터를 찾을 수 없습니다.")
    return files[-1]


def get_latest_optimal_path(ticker: str) -> str:
    return _find_latest_path(ticker, "optimal_params", [".json"])


def load_raw_from_storage(raw_path: str) -> pd.DataFrame:
    payload = load_json_compressed(raw_path)
    df = pd.DataFrame(payload.get("data", []))
    if df.empty:
        raise ValueError(f"데이터가 비어 있습니다: {raw_path}")
    return _normalize_ohlcv(df)


def list_available_tickers(data_dir: str = "data_cybos") -> List[str]:
    pattern = os.path.join(data_dir, "*_1m_2y.csv")
    tickers = []
    for p in glob.glob(pattern):
        name = os.path.basename(p)
        m = re.match(r"^([A-Z0-9]+)_1m_2y\.csv$", name)
        if m:
            tickers.append(m.group(1))
    return sorted(set(tickers))
