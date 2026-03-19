import os
import logging
from datetime import datetime
from typing import List, Optional

import pandas as pd

from app.quant.feature_engineer import IntradayFeatureEngineer
from app.quant.sources import (
    fetch_and_store_timeseries as quant_fetch_and_store_timeseries,
    get_latest_feature_path as quant_get_latest_feature_path,
    get_latest_raw_path as quant_get_latest_raw_path,
    list_available_tickers as quant_list_available_tickers,
    load_ohlcv_from_db as quant_load_ohlcv_from_db,
    load_raw_from_storage as quant_load_raw_from_storage,
)
from app.shared.infra.s3_client import s3_client
from collector.storage import get_storage_dir

logger = logging.getLogger(__name__)


def resolve_tickers(tickers: Optional[str], data_dir: str) -> List[str]:
    if tickers:
        return [t.strip() for t in tickers.split(",") if t.strip()]
    return quant_list_available_tickers(data_dir)


def build_feature_df(
    raw_path: str,
    horizon_minutes: int,
    feature_profile: str,
    recent_window_days: Optional[int],
) -> pd.DataFrame:
    return IntradayFeatureEngineer(
        horizon_minutes=horizon_minutes,
        feature_profile=feature_profile,
        recent_window_days=recent_window_days,
    ).build(quant_load_raw_from_storage(raw_path))


def save_feature_df(storage_dir: str, ticker: str, feat_df: pd.DataFrame) -> str:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    feat_path = os.path.join(storage_dir, f"feat_{ticker}_{stamp}.csv.gz")
    feat_df.to_csv(feat_path, index=False, compression="gzip")
    return feat_path


def _store_df_as_raw(ticker: str, df: pd.DataFrame) -> str:
    """DataFrame을 gzip JSON으로 storage/quant에 저장하고 경로를 반환합니다."""
    import gzip, json
    from collector.storage import get_storage_dir
    storage_dir = get_storage_dir("quant")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(storage_dir, f"raw_{ticker}_{stamp}.json.gz")
    payload = {
        "ticker": ticker,
        "rows": len(df),
        "generated_at": datetime.now().isoformat(),
        "source": "mysql",
        "data": [
            {
                "ts": row.ts.isoformat() if hasattr(row.ts, "isoformat") else str(row.ts),
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


def resolve_raw_path(ticker: str, data_dir: str, run_fetch: bool, days: int = 730) -> str:
    """OHLCV 데이터 경로를 결정합니다.

    우선순위:
      1. DB (MySQL candle_1m) - 항상 시도
      2. 기존 storage/quant 캐시  - DB 실패 시
      3. CSV 파일 (로컬 data_dir) - 최종 Fallback
    """
    # 1순위: DB에서 직접 로드
    try:
        df = quant_load_ohlcv_from_db(ticker, days=days)
        path = _store_df_as_raw(ticker, df)
        return path
    except Exception as db_exc:
        import logging
        logging.getLogger(__name__).warning(
            "[%s] DB 로드 실패, 기존 소스로 Fallback: %s", ticker, db_exc
        )

    # 2순위: 기존 storage/quant 캐시
    if not run_fetch:
        try:
            return quant_get_latest_raw_path(ticker)
        except FileNotFoundError:
            pass

    # 3순위: CSV → storage/quant 저장
    return quant_fetch_and_store_timeseries(ticker=ticker, data_dir=data_dir)


def prepare_feature_df(
    ticker: str,
    data_dir: str,
    run_fetch: bool,
    run_feature_extract: bool,
    horizon_minutes: int,
    feature_profile: str = "baseline",
    recent_window_days: Optional[int] = None,
    days: int = 730,
) -> tuple[str, str, pd.DataFrame]:
    storage_dir = get_storage_dir("quant")
    raw_path = resolve_raw_path(ticker=ticker, data_dir=data_dir, run_fetch=run_fetch, days=days)

    if run_feature_extract:
        feat_df = build_feature_df(
            raw_path=raw_path,
            horizon_minutes=horizon_minutes,
            feature_profile=feature_profile,
            recent_window_days=recent_window_days,
        )
        feat_path = save_feature_df(storage_dir=storage_dir, ticker=ticker, feat_df=feat_df)
        
        # S3 업로드 (비동기 처리가 좋지만, 일단은 직렬로 구현)
        try:
            today_str = datetime.now().strftime("%Y%m%d")
            filename = os.path.basename(feat_path)
            s3_client.upload_file(feat_path, f"features/{today_str}/{ticker}/{filename}")
        except Exception as e:
            import logging
            logging.getLogger(__name__).error("[%s] S3 업로드 실패: %s", ticker, e)
    else:
        try:
            feat_path = quant_get_latest_feature_path(ticker)
        except FileNotFoundError:
            # 로컬에 없으면 S3에서 최신 파일을 찾아 다운로드 시도
            today_str = datetime.now().strftime("%Y%m%d")
            s3_prefix = f"features/{today_str}/{ticker}/"
            logger.info("[%s] 로컬 피처 없음, S3(%s) 검색 중...", ticker, s3_prefix)
            s3_files = s3_client.list_files(s3_prefix)
            if s3_files:
                # 가장 최근 파일 (파일명 정렬 기준)
                latest_s3_key = sorted(s3_files)[-1]
                filename = os.path.basename(latest_s3_key)
                local_path = os.path.join(storage_dir, filename)
                
                # 키에서 접두사(tlu600/) 제거 (S3Client 내부에서 다시 붙임)
                # s3_client.list_files는 풀 키를 반환하므로 주의
                relative_key = latest_s3_key
                if s3_client.path_prefix and latest_s3_key.startswith(s3_client.path_prefix):
                    relative_key = latest_s3_key[len(s3_client.path_prefix):].lstrip("/")
                
                if s3_client.download_file(relative_key, local_path):
                    feat_path = local_path
                else:
                    raise FileNotFoundError(f"[{ticker}] S3 다운로드 실패")
            else:
                raise FileNotFoundError(f"[{ticker}] S3에도 피처 파일이 없습니다.")

        feat_df = pd.read_csv(feat_path)
        if "ts" in feat_df.columns:
            feat_df["ts"] = pd.to_datetime(feat_df["ts"], errors="coerce")
            feat_df = feat_df.dropna(subset=["ts"]).reset_index(drop=True)

    return raw_path, feat_path, feat_df
