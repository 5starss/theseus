import os
from datetime import datetime
from typing import List, Optional

import pandas as pd

from app.quant.feature_engineer import IntradayFeatureEngineer
from app.quant.sources import (
    fetch_and_store_timeseries as quant_fetch_and_store_timeseries,
    get_latest_feature_path as quant_get_latest_feature_path,
    get_latest_raw_path as quant_get_latest_raw_path,
    list_available_tickers as quant_list_available_tickers,
    load_raw_from_storage as quant_load_raw_from_storage,
)
from collector.storage import get_storage_dir


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


def resolve_raw_path(ticker: str, data_dir: str, run_fetch: bool) -> str:
    if run_fetch:
        return quant_fetch_and_store_timeseries(ticker=ticker, data_dir=data_dir)
    try:
        return quant_get_latest_raw_path(ticker)
    except FileNotFoundError:
        return quant_fetch_and_store_timeseries(ticker=ticker, data_dir=data_dir)


def prepare_feature_df(
    ticker: str,
    data_dir: str,
    run_fetch: bool,
    run_feature_extract: bool,
    horizon_minutes: int,
    feature_profile: str = "baseline",
    recent_window_days: Optional[int] = None,
) -> tuple[str, str, pd.DataFrame]:
    storage_dir = get_storage_dir("quant")
    raw_path = resolve_raw_path(ticker=ticker, data_dir=data_dir, run_fetch=run_fetch)

    if run_feature_extract:
        feat_df = build_feature_df(
            raw_path=raw_path,
            horizon_minutes=horizon_minutes,
            feature_profile=feature_profile,
            recent_window_days=recent_window_days,
        )
        feat_path = save_feature_df(storage_dir=storage_dir, ticker=ticker, feat_df=feat_df)
    else:
        feat_path = quant_get_latest_feature_path(ticker)
        feat_df = pd.read_csv(feat_path)
        if "ts" in feat_df.columns:
            feat_df["ts"] = pd.to_datetime(feat_df["ts"], errors="coerce")
            feat_df = feat_df.dropna(subset=["ts"]).reset_index(drop=True)

    return raw_path, feat_path, feat_df
