import logging
from dataclasses import dataclass
from typing import Any, Dict, List

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import RobustScaler

from app.quant.modeling import TimeSeriesModeler
from app.quant.sources import get_latest_feature_path

try:
    from lightgbm import LGBMClassifier
except Exception:
    LGBMClassifier = None

try:
    from xgboost import XGBClassifier
except Exception:
    XGBClassifier = None

try:
    from catboost import CatBoostClassifier
except Exception:
    CatBoostClassifier = None

logger = logging.getLogger(__name__)


@dataclass
class PanelEvalResult:
    summary: Dict[str, Any]
    time_holdout: Dict[str, Any]
    ticker_holdout: List[Dict[str, Any]]


def _load_panel_features(tickers: List[str], storage_dir: str) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for t in tickers:
        p = get_latest_feature_path(t, storage_dir)
        df = pd.read_csv(p)
        df["ts"] = pd.to_datetime(df["ts"])
        df["ticker"] = t
        frames.append(df)
    if not frames:
        raise ValueError("패널 검증 대상 피처가 없습니다.")
    panel = pd.concat(frames, ignore_index=True).sort_values(["ts", "ticker"]).reset_index(drop=True)
    return panel


def _prepare_xy(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: List[str],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    scaler = RobustScaler()
    x_train_base = train_df[feature_cols].astype(float).to_numpy()
    x_test_base = test_df[feature_cols].astype(float).to_numpy()
    x_train_base = scaler.fit_transform(x_train_base)
    x_test_base = scaler.transform(x_test_base)

    train_ticker = pd.get_dummies(train_df["ticker"], prefix="tk")
    test_ticker = pd.get_dummies(test_df["ticker"], prefix="tk")
    all_cols = sorted(set(train_ticker.columns) | set(test_ticker.columns))
    train_ticker = train_ticker.reindex(columns=all_cols, fill_value=0)
    test_ticker = test_ticker.reindex(columns=all_cols, fill_value=0)

    x_train = np.hstack([x_train_base, train_ticker.to_numpy(dtype=float)])
    x_test = np.hstack([x_test_base, test_ticker.to_numpy(dtype=float)])
    y_train = train_df["target_up"].astype(int).to_numpy()
    y_test = test_df["target_up"].astype(int).to_numpy()
    return x_train, y_train, x_test, y_test


def _build_classifier_zoo() -> Dict[str, Any]:
    models: Dict[str, Any] = {}
    if LGBMClassifier is not None:
        models["lightgbm"] = LGBMClassifier(
            n_estimators=250,
            learning_rate=0.03,
            num_leaves=31,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.2,
            reg_lambda=1.0,
            random_state=42,
            verbose=-1,
        )
    if XGBClassifier is not None:
        models["xgboost"] = XGBClassifier(
            n_estimators=300,
            learning_rate=0.03,
            max_depth=5,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="binary:logistic",
            eval_metric="logloss",
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=42,
            verbosity=0,
        )
    if CatBoostClassifier is not None:
        models["catboost"] = CatBoostClassifier(
            iterations=350,
            learning_rate=0.03,
            depth=6,
            loss_function="Logloss",
            random_seed=42,
            verbose=False,
        )
    if not models:
        models["logistic"] = LogisticRegression(max_iter=800, solver="lbfgs")
    return models


def _fit_predict_ensemble(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
) -> tuple[np.ndarray, Dict[str, float], Dict[str, float]]:
    models = _build_classifier_zoo()

    split_idx = max(1, int(len(y_train) * 0.9))
    x_sub_train = x_train[:split_idx]
    y_sub_train = y_train[:split_idx]
    x_sub_val = x_train[split_idx:]
    y_sub_val = y_train[split_idx:]
    if len(y_sub_val) == 0:
        x_sub_train = x_train
        y_sub_train = y_train
        x_sub_val = x_train
        y_sub_val = y_train

    weights_raw: Dict[str, float] = {}
    test_probs: Dict[str, np.ndarray] = {}
    for name, model in models.items():
        model.fit(x_sub_train, y_sub_train)
        val_proba = model.predict_proba(x_sub_val)[:, 1]
        val_pred = (val_proba >= 0.5).astype(int)
        val_acc = float(np.mean(val_pred == y_sub_val))
        weights_raw[name] = max(1e-6, val_acc)

        model.fit(x_train, y_train)
        test_probs[name] = model.predict_proba(x_test)[:, 1]

    total = float(sum(weights_raw.values()))
    weights = {k: float(v / total) for k, v in weights_raw.items()}
    ens_prob = np.zeros(x_test.shape[0], dtype=float)
    for name, w in weights.items():
        ens_prob += w * test_probs[name]
    return ens_prob, weights, weights_raw


def _compute_metrics(y_true: np.ndarray, prob: np.ndarray, long_th: float = 0.55, short_th: float = 0.45) -> Dict[str, float]:
    pred = (prob >= 0.5).astype(int)
    acc = float(np.mean(pred == y_true)) if len(y_true) > 0 else 0.0
    up_ratio = float(np.mean(y_true == 1)) if len(y_true) > 0 else 0.0
    baseline = max(up_ratio, 1.0 - up_ratio)

    signal = np.where(prob >= long_th, 1, np.where(prob <= short_th, -1, 0))
    trade_mask = signal != 0
    if np.any(trade_mask):
        y_dir = np.where(y_true == 1, 1, -1)
        trade_acc = float(np.mean(signal[trade_mask] == y_dir[trade_mask]))
        trade_count = int(np.sum(trade_mask))
    else:
        trade_acc = 0.0
        trade_count = 0

    return {
        "samples": float(len(y_true)),
        "accuracy_all": acc,
        "baseline_all": baseline,
        "up_ratio": up_ratio,
        "trade_count": float(trade_count),
        "trade_accuracy": trade_acc,
        "long_threshold": float(long_th),
        "short_threshold": float(short_th),
    }


def run_multi_ticker_panel_eval(
    tickers: List[str],
    storage_dir: str = "storage",
    split_ratio: float = 0.8,
) -> PanelEvalResult:
    panel = _load_panel_features(tickers, storage_dir)
    modeler = TimeSeriesModeler()
    feature_cols = [c for c in modeler.DEFAULT_FEATURES if c in panel.columns]
    if not feature_cols:
        raise ValueError("패널 검증에 사용할 피처가 없습니다.")

    split_ts = panel["ts"].quantile(split_ratio)
    logger.info("  [1/2] 전체 시간축(Time Holdout) 모델 학습 시작 (분할점: %s)...", split_ts)
    time_train = panel[panel["ts"] < split_ts].copy()
    time_test = panel[panel["ts"] >= split_ts].copy()
    x_train, y_train, x_test, y_test = _prepare_xy(time_train, time_test, feature_cols)
    prob, weights, raw = _fit_predict_ensemble(x_train, y_train, x_test)
    time_metrics = _compute_metrics(y_test, prob)
    logger.info("  [1/2] 시간축 검증 완료 | 정확도: %.4f (Base: %.4f)", time_metrics["accuracy_all"], time_metrics["baseline_all"])

    logger.info("  [2/2] 개별 종목축(Ticker Holdout) 교차 검증 시작 (총 %d 종목)...", len(tickers))
    holdout_rows: List[Dict[str, Any]] = []
    for i, holdout in enumerate(tickers, start=1):
        tr = panel[(panel["ticker"] != holdout) & (panel["ts"] < split_ts)].copy()
        te = panel[(panel["ticker"] == holdout) & (panel["ts"] >= split_ts)].copy()
        if tr.empty or te.empty:
            logger.warning("    - [%d/%d] %s: 데이터 부족으로 스킵", i, len(tickers), holdout)
            holdout_rows.append(
                {"ticker": holdout, "status": "skipped", "reason": "insufficient_rows"}
            )
            continue

        x_tr, y_tr, x_te, y_te = _prepare_xy(tr, te, feature_cols)
        h_prob, _, _ = _fit_predict_ensemble(x_tr, y_tr, x_te)
        metrics = _compute_metrics(y_te, h_prob)
        holdout_rows.append({"ticker": holdout, "status": "ok", **metrics})
        logger.info("    - [%d/%d] %s 검증 완료 | 정확도: %.4f", i, len(tickers), holdout, metrics["accuracy_all"])

    valid = [r for r in holdout_rows if r.get("status") == "ok"]
    holdout_mean_acc = float(np.mean([r["accuracy_all"] for r in valid])) if valid else 0.0
    holdout_mean_trade_acc = float(np.mean([r["trade_accuracy"] for r in valid])) if valid else 0.0

    summary = {
        "tickers": tickers,
        "rows_total": float(len(panel)),
        "split_ratio": float(split_ratio),
        "split_timestamp": str(split_ts),
        "feature_count": float(len(feature_cols)),
        "ensemble_weights_time_holdout": weights,
        "ensemble_weights_raw_time_holdout": raw,
        "time_holdout_accuracy": time_metrics["accuracy_all"],
        "time_holdout_baseline": time_metrics["baseline_all"],
        "time_holdout_trade_accuracy": time_metrics["trade_accuracy"],
        "ticker_holdout_mean_accuracy": holdout_mean_acc,
        "ticker_holdout_mean_trade_accuracy": holdout_mean_trade_acc,
    }

    logger.info(
        "패널 검증 완료 | rows=%d | time_acc=%.4f (base=%.4f) | holdout_mean=%.4f",
        len(panel),
        time_metrics["accuracy_all"],
        time_metrics["baseline_all"],
        holdout_mean_acc,
    )
    return PanelEvalResult(summary=summary, time_holdout=time_metrics, ticker_holdout=holdout_rows)
