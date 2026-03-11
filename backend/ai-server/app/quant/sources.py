"""
quant/sources.py
────────────────
주식 시계열(OHLCV) 데이터의 로드·정규화·저장·검색을 담당하는 유틸리티.

주요 기능:
  - CSV 원본 → 표준 OHLCV DataFrame 정규화
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
def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """CSV/JSON 데이터를 표준 OHLCV 포맷으로 정규화합니다.

    1. 컬럼명 공백 제거 및 소문자화
    2. 필수 컬럼 존재 여부 검증
    3. ts → datetime 변환, 중복 제거, 숫자형 캐스팅
    """
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


# ──────────────────────────────────────────────
# JSON 로드 유틸
# ──────────────────────────────────────────────
def load_json_compressed(path: str) -> dict:
    """Gzip 압축 여부를 자동으로 판단하여 JSON 데이터를 로드합니다."""
    if path.endswith(".gz"):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ──────────────────────────────────────────────
# CSV → DataFrame
# ──────────────────────────────────────────────
def get_csv_path(ticker: str, data_dir: str = "data_cybos") -> str:
    """CSV 파일의 유효한 경로를 반환합니다."""
    path = os.path.join(data_dir, f"{ticker}_1m_2y.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"CSV 파일을 찾을 수 없습니다: {path}")
    return path


def load_ohlcv_from_csv(ticker: str, data_dir: str = "data_cybos") -> pd.DataFrame:
    """국내 주식 1분봉 CSV 파일을 로드하여 정규화된 DataFrame 을 반환합니다."""
    csv_path = get_csv_path(ticker, data_dir)
    logger.info("CSV 로드 시작: %s", csv_path)
    raw = pd.read_csv(csv_path, encoding="utf-8-sig")
    df = _normalize_ohlcv(raw)
    logger.info(
        "CSV 정규화 완료: %s건 | 기간: %s ~ %s",
        len(df),
        df["ts"].iloc[0],
        df["ts"].iloc[-1],
    )
    return df


# ──────────────────────────────────────────────
# 데이터 저장 (CSV → storage/quant)
# ──────────────────────────────────────────────
def fetch_and_store_timeseries(
    ticker: str,
    data_dir: str = "data_cybos",
) -> str:
    """CSV 원본을 가공하여 압축 JSON 으로 storage/quant 에 저장합니다."""
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

    logger.info("원천 데이터 저장 완료: %s", out_path)
    return out_path


# ──────────────────────────────────────────────
# 최신 파일 경로 조회
# ──────────────────────────────────────────────
def get_latest_raw_path(ticker: str) -> str:
    """가장 최근의 raw OHLCV 파일 경로를 반환합니다."""
    return _find_latest_path(ticker, "raw", [".json", ".json.gz"])


def get_latest_feature_path(ticker: str) -> str:
    """가장 최근의 feature 파일 경로를 반환합니다."""
    return _find_latest_path(ticker, "feat", [".csv", ".csv.gz"])


def get_latest_model_path(ticker: str) -> str:
    """가장 최근의 model 파일 경로를 반환합니다."""
    regex = rf"^model_{re.escape(ticker)}_\d{{8}}_\d{{6}}\.json$"
    return _find_latest_path(ticker, "model", [".json"], regex_pattern=regex)


def get_latest_global_model_path() -> str:
    """가장 최근의 공통(global/panel) model 파일 경로를 반환합니다."""
    storage_dir = get_storage_dir(_QUANT_CATEGORY)
    pattern = os.path.join(storage_dir, "model_global_*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        raise FileNotFoundError("global model 데이터를 storage/quant 에서 찾을 수 없습니다.")
    return files[-1]


def get_latest_optimal_path(ticker: str) -> str:
    """가장 최근의 optimal_params 파일 경로를 반환합니다."""
    return _find_latest_path(ticker, "optimal_params", [".json"])


# ──────────────────────────────────────────────
# 저장된 데이터 재로드
# ──────────────────────────────────────────────
def load_raw_from_storage(raw_path: str) -> pd.DataFrame:
    """저장된 원천 JSON/GZ 데이터를 정규화된 DataFrame 으로 반환합니다."""
    payload = load_json_compressed(raw_path)
    df = pd.DataFrame(payload.get("data", []))
    if df.empty:
        raise ValueError(f"데이터가 비어 있습니다: {raw_path}")
    return _normalize_ohlcv(df)


# ──────────────────────────────────────────────
# 사용 가능한 종목 목록
# ──────────────────────────────────────────────
def list_available_tickers(data_dir: str = "data_cybos") -> List[str]:
    """data_dir 내의 CSV 파일들을 분석하여 사용 가능한 종목 코드 목록을 반환합니다."""
    pattern = os.path.join(data_dir, "*_1m_2y.csv")
    tickers = []
    for p in glob.glob(pattern):
        name = os.path.basename(p)
        m = re.match(r"^([A-Z0-9]+)_1m_2y\.csv$", name)
        if m:
            tickers.append(m.group(1))
    return sorted(set(tickers))
