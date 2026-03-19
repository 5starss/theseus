import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd

from app.quant.agent import QuantAnalysisAgent
from app.quant.backtest import recommend_parameters, run_parameter_optimization, run_walkforward_backtest
from app.quant.feature_engineer import IntradayFeatureEngineer
from app.quant.modeling import TimeSeriesModeler, load_model, save_model
from app.quant.preparation import (
    build_feature_df,
    prepare_feature_df,
    resolve_raw_path,
    resolve_tickers,
    save_feature_df,
)
from app.quant.quality import build_backtest_quality_flags
from app.quant.sources import (
    get_latest_global_model_path as quant_get_latest_global_model_path,
    get_latest_model_path as quant_get_latest_model_path,
    load_raw_from_storage as quant_load_raw_from_storage,
)
from collector.storage import get_storage_dir

def _timestamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _write_json_artifact(path: str, payload: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

def extract_features_for_ticker(
    ticker: str,
    data_dir: str,
    run_fetch: bool,
    horizon_minutes: int,
    feature_profile: str = "baseline",
    recent_window_days: Optional[int] = None,
) -> Dict[str, Any]:
    storage_dir = get_storage_dir("quant")
    raw_path, feat_path, feat_df = prepare_feature_df(
        ticker=ticker,
        data_dir=data_dir,
        run_fetch=run_fetch,
        run_feature_extract=True,
        horizon_minutes=horizon_minutes,
        feature_profile=feature_profile,
        recent_window_days=recent_window_days,
    )
    stamp = _timestamp()
    meta_path = os.path.join(storage_dir, f"feature_extract_{ticker}_{stamp}.json")
    payload = {
        "ticker": ticker,
        "generated_at": datetime.now().isoformat(),
        "source_raw_path": raw_path,
        "feature_path": feat_path,
        "horizon_minutes": horizon_minutes,
        "feature_rows": int(len(feat_df)),
        "feature_columns": list(feat_df.columns),
        "feature_profile": feature_profile,
        "recent_window_days": recent_window_days,
    }
    _write_json_artifact(meta_path, payload)

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
    feature_profile: str = "baseline",
    recent_window_days: Optional[int] = None,
) -> Dict[str, Any]:
    storage_dir = get_storage_dir("quant")
    raw_path, feat_path, feat_df = prepare_feature_df(
        ticker=ticker,
        data_dir=data_dir,
        run_fetch=run_fetch,
        run_feature_extract=run_feature_extract,
        horizon_minutes=horizon_minutes,
        feature_profile=feature_profile,
        recent_window_days=recent_window_days,
    )
    modeler = TimeSeriesModeler(model_type=model_type, feature_profile=feature_profile)
    artifact = modeler.train(feat_df)

    model_path = os.path.join(storage_dir, f"model_{ticker}_{_timestamp()}.json")
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
        "feature_profile": feature_profile,
    }


def train_global_model(
    tickers: List[str],
    data_dir: str,
    run_fetch: bool,
    run_feature_extract: bool,
    horizon_minutes: int,
    model_type: str,
    feature_profile: str = "baseline",
    recent_window_days: Optional[int] = None,
) -> Dict[str, Any]:
    """여러 종목의 데이터를 통합(Panel)하여 글로벌 공통 모델을 학습합니다."""
    storage_dir = get_storage_dir("quant")
    all_feats = []
    
    for ticker in tickers:
        _, _, feat_df = prepare_feature_df(
            ticker=ticker,
            data_dir=data_dir,
            run_fetch=run_fetch,
            run_feature_extract=run_feature_extract,
            horizon_minutes=horizon_minutes,
            feature_profile=feature_profile,
            recent_window_days=recent_window_days,
        )
        feat_df["ticker"] = ticker
        all_feats.append(feat_df)
    
    panel_df = pd.concat(all_feats, ignore_index=True).sort_values("ts").reset_index(drop=True)
    
    modeler = TimeSeriesModeler(model_type=model_type, feature_profile=feature_profile)
    artifact = modeler.train(panel_df)
    
    model_path = os.path.join(storage_dir, f"model_global_{_timestamp()}.json")
    save_model(model_path, artifact)
    
    return {
        "storage_dir": storage_dir,
        "tickers": tickers,
        "model_path": model_path,
        "metrics": artifact.metrics,
        "feature_count": len(artifact.feature_names),
        "rows_total": len(panel_df),
        "artifact": artifact,
        "feature_profile": feature_profile,
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
    feature_profile: str = "baseline",
    recent_window_days: Optional[int] = None,
    global_artifact: Optional[Any] = None,
    global_model_path: Optional[str] = None,
) -> Dict[str, Any]:
    storage_dir = get_storage_dir("quant")
    raw_path, feat_path, feat_df = prepare_feature_df(
        ticker=ticker,
        data_dir=data_dir,
        run_fetch=run_fetch,
        run_feature_extract=run_feature_extract,
        horizon_minutes=horizon_minutes,
        feature_profile=feature_profile,
        recent_window_days=recent_window_days,
    )

    pretrained_artifact = global_artifact
    model_path = global_model_path if global_model_path else None
    
    if run_train and not pretrained_artifact:
        modeler = TimeSeriesModeler(model_type=model_type, feature_profile=feature_profile)
        artifact = modeler.train(feat_df)
        model_path = os.path.join(storage_dir, f"model_{ticker}_{_timestamp()}.json")
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
        feature_profile=feature_profile,
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
        feature_profile=feature_profile,
        train_rows=train_rows,
        test_rows=test_rows,
        step_rows=step_rows,
        cost_bps=float(best["cost_bps"]),
        hold_bars=int(best["hold_bars"]),
        threshold_override=float(best["threshold"]),
        dynamic_hold=dynamic_hold,
        pretrained_artifact=artifact_for_eval,
    )

    stamp = _timestamp()
    optimal_path = os.path.join(storage_dir, f"optimal_params_{ticker}_{stamp}.json")
    opt_detail_path = os.path.join(storage_dir, f"optimization_results_{ticker}_{stamp}.csv")
    bt_summary_path = os.path.join(storage_dir, f"backtest_{ticker}_{stamp}.json")
    bt_detail_path = os.path.join(storage_dir, f"backtest_detail_{ticker}_{stamp}.csv")

    _write_json_artifact(
        optimal_path,
        {
            "ticker": ticker,
            "generated_at": datetime.now().isoformat(),
            "best_params": rec["best_params"],
            "top5": rec["top5"],
            "recommendation_reason": rec["recommendation_reason"],
        },
    )
    opt_df.to_csv(opt_detail_path, index=False)
    _write_json_artifact(
        bt_summary_path,
        {"ticker": ticker, "summary": bt_result.summary, "folds": bt_result.folds},
    )
    bt_result.detail.to_csv(bt_detail_path, index=False)

    s = bt_result.summary
    quality = build_backtest_quality_flags(s)
    return {
        "ticker": ticker,
        "model_type": model_type,
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
        "reliability_reasons": quality["reasons"],
        "confidence_band": quality["confidence_band"],
        "is_reliable_for_llm": quality["is_reliable_for_llm"],
        "feature_profile": feature_profile,
    }


def compare_model_performance_for_ticker(
    ticker: str,
    data_dir: str,
    run_fetch: bool,
    horizon_minutes: int,
    model_type: str,
    dynamic_hold: bool,
    train_rows: int,
    test_rows: int,
    step_rows: int,
) -> Dict[str, Any]:
    storage_dir = get_storage_dir("quant")
    raw_path = resolve_raw_path(ticker=ticker, data_dir=data_dir, run_fetch=run_fetch)
    raw_df = quant_load_raw_from_storage(raw_path)

    variant_specs = [
        {
            "name": "baseline_current",
            "feature_profile": "baseline",
            "recent_window_days": None,
        },
        {
            "name": "baseline_recent_1y",
            "feature_profile": "baseline",
            "recent_window_days": 365,
        },
        {
            "name": "mtf_recent_1y",
            "feature_profile": "mtf",
            "recent_window_days": 365,
        },
        {
            "name": "enhanced_recent_1y",
            "feature_profile": "enhanced",
            "recent_window_days": 365,
        },
    ]

    results: List[Dict[str, Any]] = []
    for spec in variant_specs:
        feat_df = IntradayFeatureEngineer(
            horizon_minutes=horizon_minutes,
            feature_profile=spec["feature_profile"],
            recent_window_days=spec["recent_window_days"],
        ).build(raw_df)
        opt_df = run_parameter_optimization(
            feat_df=feat_df,
            model_type=model_type,
            feature_profile=spec["feature_profile"],
            train_rows=train_rows,
            test_rows=test_rows,
            step_rows=step_rows,
            dynamic_hold=dynamic_hold,
        )
        rec = recommend_parameters(opt_df)
        best = rec["best_params"]
        bt = run_walkforward_backtest(
            feat_df=feat_df,
            model_type=model_type,
            feature_profile=spec["feature_profile"],
            train_rows=train_rows,
            test_rows=test_rows,
            step_rows=step_rows,
            cost_bps=float(best["cost_bps"]),
            hold_bars=int(best["hold_bars"]),
            threshold_override=float(best["threshold"]),
            dynamic_hold=dynamic_hold,
        )
        summary = dict(bt.summary)
        summary["variant"] = spec["name"]
        summary["feature_profile"] = spec["feature_profile"]
        summary["recent_window_days"] = spec["recent_window_days"]
        summary["best_params"] = best
        results.append(summary)

    baseline = next((r for r in results if r["variant"] == "baseline_current"), None)
    baseline_recent = next((r for r in results if r["variant"] == "baseline_recent_1y"), None)
    deltas: List[Dict[str, Any]] = []
    for row in results:
        delta_row = {"variant": row["variant"]}
        if baseline is not None:
            delta_row.update(
                {
                    "delta_sharpe_vs_baseline_current": float(row.get("sharpe", 0.0) - baseline.get("sharpe", 0.0)),
                    "delta_cum_return_vs_baseline_current": float(row.get("cum_return", 0.0) - baseline.get("cum_return", 0.0)),
                    "delta_win_rate_vs_baseline_current": float(row.get("win_rate", 0.0) - baseline.get("win_rate", 0.0)),
                    "delta_dir_acc_vs_baseline_current": float(row.get("directional_accuracy_all", 0.0) - baseline.get("directional_accuracy_all", 0.0)),
                    "delta_max_drawdown_vs_baseline_current": float(row.get("max_drawdown", 0.0) - baseline.get("max_drawdown", 0.0)),
                }
            )
        if baseline_recent is not None:
            delta_row.update(
                {
                    "delta_sharpe_vs_baseline_recent_1y": float(row.get("sharpe", 0.0) - baseline_recent.get("sharpe", 0.0)),
                    "delta_cum_return_vs_baseline_recent_1y": float(row.get("cum_return", 0.0) - baseline_recent.get("cum_return", 0.0)),
                    "delta_win_rate_vs_baseline_recent_1y": float(row.get("win_rate", 0.0) - baseline_recent.get("win_rate", 0.0)),
                    "delta_dir_acc_vs_baseline_recent_1y": float(row.get("directional_accuracy_all", 0.0) - baseline_recent.get("directional_accuracy_all", 0.0)),
                    "delta_max_drawdown_vs_baseline_recent_1y": float(row.get("max_drawdown", 0.0) - baseline_recent.get("max_drawdown", 0.0)),
                }
            )
        deltas.append(delta_row)

    stamp = _timestamp()
    report_path = os.path.join(storage_dir, f"performance_compare_{ticker}_{stamp}.json")
    _write_json_artifact(
        report_path,
        {
            "ticker": ticker,
            "generated_at": datetime.now().isoformat(),
            "raw_path": raw_path,
            "model_type": model_type,
            "dynamic_hold": dynamic_hold,
            "train_rows": train_rows,
            "test_rows": test_rows,
            "step_rows": step_rows,
            "variants": results,
            "deltas": deltas,
        },
    )

    recent_results = [r for r in results if r.get("recent_window_days") == 365]
    best_variant = max(results, key=lambda x: (float(x.get("sharpe", 0.0)), float(x.get("cum_return", 0.0))))
    best_recent_variant = max(recent_results, key=lambda x: (float(x.get("sharpe", 0.0)), float(x.get("cum_return", 0.0)))) if recent_results else best_variant
    return {
        "ticker": ticker,
        "raw_path": raw_path,
        "report_path": report_path,
        "variants": results,
        "deltas": deltas,
        "best_variant": best_variant["variant"],
        "best_recent_variant": best_recent_variant["variant"],
    }


def compare_model_performance_for_universe(
    tickers: List[str],
    data_dir: str,
    run_fetch: bool,
    horizon_minutes: int,
    model_type: str,
    dynamic_hold: bool,
    train_rows: int,
    test_rows: int,
    step_rows: int,
) -> Dict[str, Any]:
    storage_dir = get_storage_dir("quant")
    reports: List[Dict[str, Any]] = []
    failures: List[Dict[str, str]] = []

    for ticker in tickers:
        try:
            reports.append(
                compare_model_performance_for_ticker(
                    ticker=ticker,
                    data_dir=data_dir,
                    run_fetch=run_fetch,
                    horizon_minutes=horizon_minutes,
                    model_type=model_type,
                    dynamic_hold=dynamic_hold,
                    train_rows=train_rows,
                    test_rows=test_rows,
                    step_rows=step_rows,
                )
            )
        except Exception as exc:
            failures.append({"ticker": ticker, "error": str(exc)})

    aggregate_rows: List[Dict[str, Any]] = []
    variant_names = sorted({v["variant"] for report in reports for v in report["variants"]})
    for variant_name in variant_names:
        variant_metrics = []
        for report in reports:
            found = next((v for v in report["variants"] if v["variant"] == variant_name), None)
            if found is not None:
                variant_metrics.append(found)
        if not variant_metrics:
            continue
        aggregate_rows.append(
            {
                "variant": variant_name,
                "ticker_count": len(variant_metrics),
                "avg_sharpe": float(sum(v.get("sharpe", 0.0) for v in variant_metrics) / len(variant_metrics)),
                "avg_cum_return": float(sum(v.get("cum_return", 0.0) for v in variant_metrics) / len(variant_metrics)),
                "avg_win_rate": float(sum(v.get("win_rate", 0.0) for v in variant_metrics) / len(variant_metrics)),
                "avg_max_drawdown": float(sum(v.get("max_drawdown", 0.0) for v in variant_metrics) / len(variant_metrics)),
            }
        )

    delta_rows: List[Dict[str, Any]] = []
    delta_variant_names = sorted({d["variant"] for report in reports for d in report["deltas"]})
    for variant_name in delta_variant_names:
        variant_deltas = []
        for report in reports:
            found = next((d for d in report["deltas"] if d["variant"] == variant_name), None)
            if found is not None:
                variant_deltas.append(found)
        if not variant_deltas:
            continue
        keys = [k for k in variant_deltas[0].keys() if k != "variant"]
        row: Dict[str, Any] = {"variant": variant_name, "ticker_count": len(variant_deltas)}
        for key in keys:
            row[f"avg_{key}"] = float(sum(d.get(key, 0.0) for d in variant_deltas) / len(variant_deltas))
        delta_rows.append(row)

    best_recent_counts: Dict[str, int] = {}
    for report in reports:
        key = report["best_recent_variant"]
        best_recent_counts[key] = best_recent_counts.get(key, 0) + 1

    stamp = _timestamp()
    report_path = os.path.join(storage_dir, f"performance_compare_universe_{stamp}.json")
    _write_json_artifact(
        report_path,
        {
            "tickers": tickers,
            "generated_at": datetime.now().isoformat(),
            "model_type": model_type,
            "dynamic_hold": dynamic_hold,
            "train_rows": train_rows,
            "test_rows": test_rows,
            "step_rows": step_rows,
            "reports": reports,
            "aggregate_variants": aggregate_rows,
            "aggregate_deltas": delta_rows,
            "best_recent_variant_counts": best_recent_counts,
            "failures": failures,
        },
    )

    return {
        "tickers_total": len(tickers),
        "success_count": len(reports),
        "failure_count": len(failures),
        "report_path": report_path,
        "aggregate_variants": aggregate_rows,
        "aggregate_deltas": delta_rows,
        "best_recent_variant_counts": best_recent_counts,
        "failures": failures,
    }


def _build_quant_evidence_payload(latest_row: Dict[str, Any]) -> Dict[str, Any]:
    """LLM에 전달할 핵심 MTF 지표만 남겨 페이로드를 축소합니다."""
    allowed_keys = {
        "ts",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "ret_1m",
        "mom_5",
        "mom_15",
        "macd",
        "macd_signal",
        "macd_hist",
        "bb_width",
        "bb_pct_b",
        "rsi_14",
        "vwap",
        "dist_vwap",
        "vol_5",
        "vol_20",
        "volume_z20",
        "rv_30",
        "skew_30",
        "session_progress",
        "close_high_ratio",
        "close_low_ratio",
        "price_accel",
        "mom_vol_interaction",
        "rsi_momentum_cross",
    }
    evidence: Dict[str, Any] = {}
    for key, value in latest_row.items():
        if key == "target_return":
            continue
        if key in allowed_keys or key.startswith("mtf_"):
            if isinstance(value, pd.Timestamp):
                evidence[key] = value.isoformat()
            elif pd.isna(value):
                evidence[key] = None
            else:
                evidence[key] = value
    return evidence


def generate_quant_signal(ticker: str, data_dir: str, run_fetch: bool = True, horizon_minutes: int = 5) -> Dict[str, Any]:
    """MTF 기술적 지표를 기반으로 LLM이 분석한 퀀트 신호를 생성합니다.
    S3 업로드를 지원하는 prepare_feature_df를 사용합니다.
    """
    try:
        raw_path, feat_path, feat_df = prepare_feature_df(
            ticker=ticker,
            data_dir=data_dir,
            run_fetch=run_fetch,
            run_feature_extract=True,  # 실시간 호출 시에도 피처 추출 및 S3 업로드 수행
            horizon_minutes=horizon_minutes,
            feature_profile="mtf",
            recent_window_days=None,
        )
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error("[%s] 피처 추출 실패: %s", ticker, exc)
        card = QuantAnalysisAgent._fallback_card(ticker, f"피처 생성 실패: {str(exc)}")
        return {
            "status": "ok",
            "analysis_card": card,
            "quant_evidence": {"error": str(exc)},
            "raw_result": {"mode": "mtf_llm_mvp", "feature_profile": "mtf"},
        }

    if feat_df.empty:
        card = QuantAnalysisAgent._fallback_card(ticker, "피처 생성 후 데이터 없음")
        return {
            "status": "ok",
            "analysis_card": card,
            "quant_evidence": {},
            "raw_result": {"mode": "mtf_llm_mvp", "raw_path": raw_path, "feature_profile": "mtf"},
        }

    latest_row = feat_df.iloc[-1].to_dict()
    clean_evidence = _build_quant_evidence_payload(latest_row)

    agent = QuantAnalysisAgent()
    card = agent.generate_analysis_card(ticker=ticker, quant_evidence=clean_evidence)
    return {
        "status": "ok",
        "analysis_card": card,
        "quant_evidence": clean_evidence,
        "raw_result": {
            "mode": "mtf_llm_mvp",
            "raw_path": raw_path,
            "feature_profile": "mtf",
            "feature_rows": int(len(feat_df)),
            "horizon_minutes": horizon_minutes,
            "evidence_keys": list(clean_evidence.keys()),
        },
    }
