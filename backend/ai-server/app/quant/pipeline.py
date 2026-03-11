import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from app.quant.backtest import recommend_parameters, run_parameter_optimization, run_walkforward_backtest
from app.quant.feature_engineer import IntradayFeatureEngineer
from app.quant.modeling import TimeSeriesModeler, load_model, save_model
from app.quant.sources import (
    fetch_and_store_timeseries as quant_fetch_and_store_timeseries,
    get_latest_feature_path as quant_get_latest_feature_path,
    get_latest_global_model_path as quant_get_latest_global_model_path,
    get_latest_model_path as quant_get_latest_model_path,
    get_latest_raw_path as quant_get_latest_raw_path,
    list_available_tickers as quant_list_available_tickers,
    load_raw_from_storage as quant_load_raw_from_storage,
)
from collector.storage import get_storage_dir


def resolve_tickers(tickers: Optional[str], data_dir: str) -> List[str]:
    if tickers:
        return [t.strip() for t in tickers.split(",") if t.strip()]
    return quant_list_available_tickers(data_dir)


def extract_features_for_ticker(
    ticker: str,
    data_dir: str,
    run_fetch: bool,
    horizon_minutes: int,
) -> Dict[str, Any]:
    storage_dir = get_storage_dir("quant")
    raw_path = _resolve_raw_path(ticker=ticker, data_dir=data_dir, run_fetch=run_fetch)
    feat_df = IntradayFeatureEngineer(horizon_minutes=horizon_minutes).build(
        quant_load_raw_from_storage(raw_path)
    )
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    feat_path = os.path.join(storage_dir, f"feat_{ticker}_{stamp}.csv.gz")
    feat_df.to_csv(feat_path, index=False, compression="gzip")

    meta_path = os.path.join(storage_dir, f"feature_extract_{ticker}_{stamp}.json")
    payload = {
        "ticker": ticker,
        "generated_at": datetime.now().isoformat(),
        "source_raw_path": raw_path,
        "feature_path": feat_path,
        "horizon_minutes": horizon_minutes,
        "feature_rows": int(len(feat_df)),
        "feature_columns": list(feat_df.columns),
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return {
        "storage_dir": storage_dir,
        "raw_path": raw_path,
        "feature_path": feat_path,
        "feature_rows": int(len(feat_df)),
        "feature_columns": list(feat_df.columns),
        "meta_path": meta_path,
        "feature_df": feat_df,
    }


def train_for_ticker(
    ticker: str,
    data_dir: str,
    run_fetch: bool,
    run_feature_extract: bool,
    horizon_minutes: int,
    model_type: str,
) -> Dict[str, Any]:
    storage_dir = get_storage_dir("quant")
    raw_path, feat_path, feat_df = _prepare_feature_df(
        ticker=ticker,
        data_dir=data_dir,
        run_fetch=run_fetch,
        run_feature_extract=run_feature_extract,
        horizon_minutes=horizon_minutes,
    )
    modeler = TimeSeriesModeler(model_type=model_type)
    artifact = modeler.train(feat_df)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = os.path.join(storage_dir, f"model_{ticker}_{stamp}.json")
    save_model(model_path, artifact)

    return {
        "storage_dir": storage_dir,
        "raw_path": raw_path,
        "feature_path": feat_path,
        "model_path": model_path,
        "metrics": artifact.metrics,
        "feature_count": len(artifact.feature_names),
        "feature_names": artifact.feature_names,
        "threshold": artifact.threshold,
    }


def train_global_model(
    tickers: List[str],
    data_dir: str,
    run_fetch: bool,
    run_feature_extract: bool,
    horizon_minutes: int,
    model_type: str,
) -> Dict[str, Any]:
    """여러 종목의 데이터를 통합(Panel)하여 글로벌 공통 모델을 학습합니다."""
    storage_dir = get_storage_dir("quant")
    all_feats = []
    
    for ticker in tickers:
        _, _, feat_df = _prepare_feature_df(
            ticker=ticker,
            data_dir=data_dir,
            run_fetch=run_fetch,
            run_feature_extract=run_feature_extract,
            horizon_minutes=horizon_minutes,
        )
        feat_df["ticker"] = ticker
        all_feats.append(feat_df)
    
    panel_df = pd.concat(all_feats, ignore_index=True).sort_values("ts").reset_index(drop=True)
    
    modeler = TimeSeriesModeler(model_type=model_type)
    artifact = modeler.train(panel_df)
    
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_path = os.path.join(storage_dir, f"model_global_{stamp}.json")
    save_model(model_path, artifact)
    
    return {
        "storage_dir": storage_dir,
        "tickers": tickers,
        "model_path": model_path,
        "metrics": artifact.metrics,
        "feature_count": len(artifact.feature_names),
        "rows_total": len(panel_df),
        "artifact": artifact,
    }


def load_latest_global_model() -> Dict[str, Any]:
    model_path = quant_get_latest_global_model_path()
    artifact = load_model(model_path)
    return {"model_path": model_path, "artifact": artifact}


def run_adaptive_winrate_for_ticker(
    ticker: str,
    data_dir: str,
    run_fetch: bool,
    run_feature_extract: bool,
    run_train: bool,
    use_pretrained: bool,
    model_type: str,
    dynamic_hold: bool,
    train_rows: int,
    test_rows: int,
    step_rows: int,
    horizon_minutes: int,
    global_artifact: Optional[Any] = None,
    global_model_path: Optional[str] = None,
) -> Dict[str, Any]:
    storage_dir = get_storage_dir("quant")
    raw_path, feat_path, feat_df = _prepare_feature_df(
        ticker=ticker,
        data_dir=data_dir,
        run_fetch=run_fetch,
        run_feature_extract=run_feature_extract,
        horizon_minutes=horizon_minutes,
    )

    pretrained_artifact = global_artifact
    model_path = global_model_path if global_model_path else None
    
    if run_train and not pretrained_artifact:
        modeler = TimeSeriesModeler(model_type=model_type)
        artifact = modeler.train(feat_df)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_path = os.path.join(storage_dir, f"model_{ticker}_{stamp}.json")
        save_model(model_path, artifact)
        pretrained_artifact = artifact
    elif not pretrained_artifact and use_pretrained:
        try:
            model_path = quant_get_latest_model_path(ticker)
            pretrained_artifact = load_model(model_path)
        except Exception:
            pretrained_artifact = None

    artifact_for_eval = pretrained_artifact if (global_artifact is not None or use_pretrained) else None

    opt_df = run_parameter_optimization(
        feat_df=feat_df,
        model_type=model_type,
        train_rows=train_rows,
        test_rows=test_rows,
        step_rows=step_rows,
        dynamic_hold=dynamic_hold,
        pretrained_artifact=artifact_for_eval,
    )
    rec = recommend_parameters(opt_df)
    best = rec["best_params"]

    bt_result = run_walkforward_backtest(
        feat_df=feat_df,
        model_type=model_type,
        train_rows=train_rows,
        test_rows=test_rows,
        step_rows=step_rows,
        cost_bps=float(best["cost_bps"]),
        hold_bars=int(best["hold_bars"]),
        threshold_override=float(best["threshold"]),
        dynamic_hold=dynamic_hold,
        pretrained_artifact=artifact_for_eval,
    )

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    optimal_path = os.path.join(storage_dir, f"optimal_params_{ticker}_{stamp}.json")
    opt_detail_path = os.path.join(storage_dir, f"optimization_results_{ticker}_{stamp}.csv")
    bt_summary_path = os.path.join(storage_dir, f"backtest_{ticker}_{stamp}.json")
    bt_detail_path = os.path.join(storage_dir, f"backtest_detail_{ticker}_{stamp}.csv")

    with open(optimal_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "ticker": ticker,
                "generated_at": datetime.now().isoformat(),
                "best_params": rec["best_params"],
                "top5": rec["top5"],
                "recommendation_reason": rec["recommendation_reason"],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    opt_df.to_csv(opt_detail_path, index=False)
    with open(bt_summary_path, "w", encoding="utf-8") as f:
        json.dump(
            {"ticker": ticker, "summary": bt_result.summary, "folds": bt_result.folds},
            f,
            ensure_ascii=False,
            indent=2,
        )
    bt_result.detail.to_csv(bt_detail_path, index=False)

    s = bt_result.summary
    quality = build_backtest_quality_flags(s)
    return {
        "ticker": ticker,
        "raw_path": raw_path,
        "feature_path": feat_path,
        "model_path": model_path,
        "optimal_path": optimal_path,
        "backtest_summary_path": bt_summary_path,
        "best_params": best,
        "win_rate": float(s.get("win_rate", 0.0)),
        "trade_count": int(s.get("trade_count", 0)),
        "cum_return": float(s.get("cum_return", 0.0)),
        "sharpe": float(s.get("sharpe", 0.0)),
        "directional_accuracy_all": float(s.get("directional_accuracy_all", 0.0)),
        "directional_baseline_all": float(s.get("directional_baseline_all", 0.0)),
        "quality_flags": quality["flags"],
        "confidence_band": quality["confidence_band"],
        "is_reliable_for_llm": quality["is_reliable_for_llm"],
    }


def build_backtest_quality_flags(summary: Dict[str, Any]) -> Dict[str, Any]:
    trade_count = int(summary.get("trade_count", 0))
    sharpe = float(summary.get("sharpe", 0.0))
    dir_acc = float(summary.get("directional_accuracy_all", 0.0))
    dir_base = float(summary.get("directional_baseline_all", 0.0))
    exposure = float(summary.get("exposure", 0.0))

    flags: List[str] = []
    if trade_count < 100:
        flags.append("LOW_SAMPLE_SIZE")
    if sharpe > 8.0:
        flags.append("EXTREME_SHARPE")
    if not (0.0 <= dir_acc <= 1.0 and 0.0 <= dir_base <= 1.0):
        flags.append("DIRECTION_METRIC_OUT_OF_RANGE")
    if abs(dir_acc - dir_base) > 0.35:
        flags.append("DIRECTION_GAP_TOO_LARGE")
    if exposure < 0.02:
        flags.append("LOW_EXPOSURE")

    if "LOW_SAMPLE_SIZE" in flags or "DIRECTION_METRIC_OUT_OF_RANGE" in flags:
        confidence_band = "low"
    elif "EXTREME_SHARPE" in flags or "DIRECTION_GAP_TOO_LARGE" in flags:
        confidence_band = "medium"
    else:
        confidence_band = "high"

    return {
        "flags": flags,
        "confidence_band": confidence_band,
        "is_reliable_for_llm": confidence_band != "low",
    }


def _resolve_raw_path(ticker: str, data_dir: str, run_fetch: bool) -> str:
    if run_fetch:
        return quant_fetch_and_store_timeseries(ticker=ticker, data_dir=data_dir)
    try:
        return quant_get_latest_raw_path(ticker)
    except FileNotFoundError:
        return quant_fetch_and_store_timeseries(ticker=ticker, data_dir=data_dir)


def _prepare_feature_df(
    ticker: str,
    data_dir: str,
    run_fetch: bool,
    run_feature_extract: bool,
    horizon_minutes: int,
) -> tuple[str, str, pd.DataFrame]:
    storage_dir = get_storage_dir("quant")
    raw_path = _resolve_raw_path(ticker=ticker, data_dir=data_dir, run_fetch=run_fetch)

    if run_feature_extract:
        feat_df = IntradayFeatureEngineer(horizon_minutes=horizon_minutes).build(
            quant_load_raw_from_storage(raw_path)
        )
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        feat_path = os.path.join(storage_dir, f"feat_{ticker}_{stamp}.csv.gz")
        feat_df.to_csv(feat_path, index=False, compression="gzip")
    else:
        feat_path = quant_get_latest_feature_path(ticker)
        feat_df = pd.read_csv(feat_path)
        if "ts" in feat_df.columns:
            feat_df["ts"] = pd.to_datetime(feat_df["ts"], errors="coerce")
            feat_df = feat_df.dropna(subset=["ts"]).reset_index(drop=True)

    return raw_path, feat_path, feat_df
