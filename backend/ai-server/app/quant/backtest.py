import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler

from app.quant.modeling import LinearModelArtifact, TimeSeriesModeler

# Optional ML libraries
try:
    from lightgbm import LGBMRegressor
except ImportError:
    LGBMRegressor = None

try:
    from xgboost import XGBRegressor
except ImportError:
    XGBRegressor = None

try:
    from catboost import CatBoostRegressor
except ImportError:
    CatBoostRegressor = None

logger = logging.getLogger(__name__)


# --- Data Structures ---

@dataclass
class BacktestResult:
    """백테스트 실행 결과를 담는 데이터 클래스"""
    summary: Dict[str, Any]
    folds: List[Dict[str, Any]]
    detail: pd.DataFrame


@dataclass
class FoldCache:
    """최적화 속도 향상을 위해 각 폴드의 예측값과 타겟 컬럼을 캐싱하는 클래스"""
    fold: int
    pred: np.ndarray
    target: np.ndarray
    close: np.ndarray
    rv30: Optional[np.ndarray]
    samples: int
    up_ratio: float
    directional_accuracy: float
    buy_hold_return: float
    rv_p25: Optional[float]
    rv_p75: Optional[float]
    baseline_volatility: float = 0.0  # 학습 구간의 target_return 표준편차 (변동성 기준)


# --- Performance Calculation Helpers ---

def _cum_return_np(arr: np.ndarray) -> float:
    """누적 수익률 계산 (Numpy 기반 벡터화)"""
    if arr.size == 0:
        return 0.0
    return float(np.prod(1.0 + arr.astype(float)) - 1.0)


def _safe_sharpe_np(arr: np.ndarray, periods_per_year: int) -> float:
    """연율화된 샤프 지수 계산 (Numpy 기반)"""
    if arr.size == 0:
        return 0.0
    mean_r = float(np.mean(arr))
    std_r = float(np.std(arr))
    return float((mean_r / std_r) * np.sqrt(periods_per_year)) if std_r > 1e-12 else 0.0


def _max_drawdown_np(arr: np.ndarray) -> float:
    """최대 낙폭(MDD) 계산 (Numpy 기반)"""
    if arr.size == 0:
        return 0.0
    equity = np.cumprod(1.0 + arr.astype(float))
    peak = np.maximum.accumulate(equity)
    drawdown = np.where(peak > 0, equity / peak - 1.0, 0.0)
    return float(np.min(drawdown)) if drawdown.size > 0 else 0.0


def _calc_metrics(
    detail: pd.DataFrame,
    trades: pd.DataFrame,
    periods_per_year: int,
    buy_hold_return: Optional[float] = None,
) -> Dict[str, Any]:
    """상세 매매 로그와 전체 데이터를 바탕으로 성과 지표를 산출합니다."""
    strat_r = trades["strategy_return"].astype(float) if (not trades.empty and "strategy_return" in trades.columns) else pd.Series(dtype=float)
    long_r = trades["long_only_return"].astype(float) if (not trades.empty and "long_only_return" in trades.columns) else pd.Series(dtype=float)
    short_r = trades["short_only_return"].astype(float) if (not trades.empty and "short_only_return" in trades.columns) else pd.Series(dtype=float)

    if not detail.empty and {"pred_return", "target_return"}.issubset(detail.columns):
        direction_all = float((np.sign(detail["pred_return"]) == np.sign(detail["target_return"])).mean())
        up_ratio_all = float((detail["target_return"] > 0).mean())
    else:
        direction_all = 0.0
        up_ratio_all = 0.0
    baseline_direction_all = max(up_ratio_all, 1.0 - up_ratio_all) if not detail.empty else 0.0

    trade_count = int(len(trades))
    win_rate = float((strat_r > 0).mean()) if trade_count > 0 else 0.0
    avg_trade_return = float(strat_r.mean()) if trade_count > 0 else 0.0
    hit_count = int((strat_r > 0).sum()) if trade_count > 0 else 0

    long_only_cum = float(buy_hold_return) if buy_hold_return is not None else _cum_return_np(long_r.to_numpy())
    short_only_cum = float(-buy_hold_return) if buy_hold_return is not None else _cum_return_np(short_r.to_numpy())

    return {
        "samples": float(len(detail)),
        "trade_count": float(trade_count),
        "cum_return": _cum_return_np(strat_r.to_numpy()),
        "long_only_cum_return": long_only_cum,
        "short_only_cum_return": short_only_cum,
        "alpha_vs_long_only": _cum_return_np(strat_r.to_numpy()) - long_only_cum,
        "sharpe": _safe_sharpe_np(strat_r.to_numpy(), periods_per_year),
        "max_drawdown": _max_drawdown_np(strat_r.to_numpy()),
        "win_rate": win_rate,
        "avg_trade_return": avg_trade_return,
        "winning_trades": float(hit_count),
        "directional_accuracy_all": direction_all,
        "directional_baseline_all": baseline_direction_all,
        "up_ratio_all": up_ratio_all,
        "exposure": (float(trade_count) / float(len(detail))) if len(detail) > 0 else 0.0,
    }


# --- Model Fitting Helpers ---

def _predict_safe(model: Any, x: np.ndarray, feature_cols: List[str]) -> np.ndarray:
    """
    sklearn 래퍼 모델의 feature name 기대치와 입력 포맷을 맞춰 경고를 방지합니다.
    """
    try:
        names_in = getattr(model, "feature_names_in_", None)
        if names_in is not None and len(names_in) == x.shape[1]:
            return model.predict(pd.DataFrame(x, columns=list(names_in)))
    except Exception:
        pass
    return model.predict(x)


def _fit_predict_fold_model(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: List[str],
    model_type: str,
    cost_bps: float = 1.0,
    pretrained_artifact: Optional[LinearModelArtifact] = None,
) -> Tuple[np.ndarray, float]:
    """한 폴드(Train/Test 셋)에 대해 모델을 학습하고 예측값을 반환합니다."""
    
    def optimize_threshold_profitability(y_true: np.ndarray, y_pred: np.ndarray, cost_bps_local: float) -> float:
        """훈련 데이터에서 거래 비용을 제외한 수익을 최대로 하는 임계값을 탐색합니다."""
        cand = np.linspace(0.0, float(np.std(y_pred)) if np.std(y_pred) > 0 else 0.001, 40)
        best_t = 0.0
        best_profit = -np.inf
        cost = 2.0 * (cost_bps_local / 10000.0)
        for t in cand:
            signal = np.where(y_pred > t, 1, np.where(y_pred < -t, -1, 0))
            mask = signal != 0
            if not np.any(mask): continue
            profit = float(np.sum(signal[mask] * y_true[mask]) - (np.sum(mask) * cost))
            if profit > best_profit:
                best_profit = profit
                best_t = float(t)
        return best_t

    scaler = RobustScaler()
    x_train_raw = train_df[feature_cols].astype(float).to_numpy()
    y_train = train_df["target_return"].astype(float).to_numpy()
    x_test_raw = test_df[feature_cols].astype(float).to_numpy()

    # --- Pretrained Model Use ---
    if pretrained_artifact is not None and pretrained_artifact._runtime_models:
        if pretrained_artifact.scaler_center and pretrained_artifact.scaler_scale:
            center = np.array(pretrained_artifact.scaler_center, dtype=float)
            scale = np.array(pretrained_artifact.scaler_scale, dtype=float)
            safe_scale = np.where(np.abs(scale) > 1e-12, scale, 1.0)
            x_train = (x_train_raw - center) / safe_scale
            x_test = (x_test_raw - center) / safe_scale
        else:
            scaler.fit(x_train_raw)
            x_train = scaler.transform(x_train_raw)
            x_test = scaler.transform(x_test_raw)

        weights = pretrained_artifact.ensemble_weights or {k: 1.0/len(pretrained_artifact._runtime_models) for k in pretrained_artifact._runtime_models}
        pred = np.zeros(x_test.shape[0], dtype=float)
        pred_train = np.zeros(x_train.shape[0], dtype=float)
        for name, model in pretrained_artifact._runtime_models.items():
            w = weights.get(name, 0.0)
            p_test = _predict_safe(model, x_test, feature_cols)
            p_train = _predict_safe(model, x_train, feature_cols)
            pred += w * p_test
            pred_train += w * p_train
        
        threshold = optimize_threshold_profitability(y_train, pred_train, cost_bps)
        return pred, threshold

    # --- Fold-specific Training ---
    scaler.fit(x_train_raw)
    x_train = scaler.transform(x_train_raw)
    x_test = scaler.transform(x_test_raw)

    if model_type == "linear":
        x_train_aug = np.hstack([x_train, np.ones((x_train.shape[0], 1))])
        coeffs_aug, *_ = np.linalg.lstsq(x_train_aug, y_train, rcond=None)
        coeffs, intercept = coeffs_aug[:-1], float(coeffs_aug[-1])
        pred = x_test @ coeffs + intercept
        pred_train = x_train @ coeffs + intercept
        threshold = optimize_threshold_profitability(y_train, pred_train, cost_bps)
        return pred, threshold

    # Ensemble Training
    preds, tr_preds = {}, {}
    # LightGBM
    if LGBMRegressor is not None:
        lgbm = LGBMRegressor(n_estimators=250, learning_rate=0.03, verbose=-1, random_state=42)
        lgbm.fit(x_train, y_train)
        preds["lightgbm"] = _predict_safe(lgbm, x_test, feature_cols)
        tr_preds["lightgbm"] = _predict_safe(lgbm, x_train, feature_cols)
    # XGBoost
    if XGBRegressor is not None:
        xgb = XGBRegressor(n_estimators=300, learning_rate=0.03, verbosity=0, random_state=42)
        xgb.fit(x_train, y_train)
        preds["xgboost"] = _predict_safe(xgb, x_test, feature_cols)
        tr_preds["xgboost"] = _predict_safe(xgb, x_train, feature_cols)
    # CatBoost
    if CatBoostRegressor is not None:
        cat = CatBoostRegressor(iterations=350, learning_rate=0.03, verbose=False, random_seed=42)
        cat.fit(x_train, y_train)
        preds["catboost"] = _predict_safe(cat, x_test, feature_cols)
        tr_preds["catboost"] = _predict_safe(cat, x_train, feature_cols)

    if not preds: # Fallback to linear
        x_train_aug = np.hstack([x_train, np.ones((x_train.shape[0], 1))])
        coeffs_aug, *_ = np.linalg.lstsq(x_train_aug, y_train, rcond=None)
        pred = x_test @ coeffs_aug[:-1] + coeffs_aug[-1]
        threshold = optimize_threshold_profitability(y_train, x_train @ coeffs_aug[:-1] + coeffs_aug[-1], cost_bps)
        return pred, threshold

    # Simple Ensemble Weights based on Train Accuracy
    up_ratio = float(np.mean(y_train > 0))
    baseline = max(up_ratio, 1.0 - up_ratio)
    raw_scores = {}
    for name, p in tr_preds.items():
        dir_acc = float(np.mean(np.sign(p) == np.sign(y_train)))
        raw_scores[name] = max(1e-6, 0.7*dir_acc + 0.3*max(dir_acc - baseline, 0))
    
    score_sum = sum(raw_scores.values())
    pred = sum((raw_scores[name]/score_sum) * p for name, p in preds.items())
    pred_train = sum((raw_scores[name]/score_sum) * p for name, p in tr_preds.items())
    threshold = optimize_threshold_profitability(y_train, pred_train, cost_bps)
    return pred, threshold


# --- Iterative Backtest & Grid Logic ---

def _build_trade_index(dynamic_holds: np.ndarray) -> np.ndarray:
    """비중첩 트레이드를 위한 인덱스 생성 (동적 홀딩 지원)"""
    if len(dynamic_holds) == 0: return np.array([], dtype=int)
    idx_list, i, n = [], 0, len(dynamic_holds)
    while i < n:
        idx_list.append(i)
        i += max(1, int(dynamic_holds[i]))
    return np.array(idx_list, dtype=int)


def _evaluate_fold_from_cache(
    fold: FoldCache,
    threshold: float,
    hold_bars: int,
    cost_rate: float,
    dynamic_hold: bool,
    periods_per_year: int,
) -> Tuple[Dict[str, float], np.ndarray]:
    """캐시된 폴드 데이터를 사용하여 특정 파라미터 조합의 성과를 평가합니다."""
    signal = np.where(fold.pred > threshold, 1, np.where(fold.pred < -threshold, -1, 0)).astype(int)
    n = fold.samples

    if dynamic_hold and fold.rv30 is not None and fold.rv_p25 is not None and fold.rv_p75 is not None:
        dynamic_holds = np.where(
            fold.rv30 > fold.rv_p75, max(3, hold_bars - 2),
            np.where(fold.rv30 < fold.rv_p25, min(15, hold_bars + 3), hold_bars)
        ).astype(int)
        entry_idx = _build_trade_index(dynamic_holds)
        hold_used = dynamic_holds[entry_idx] if entry_idx.size > 0 else np.array([], dtype=int)
    else:
        entry_idx = np.arange(0, n, max(1, hold_bars), dtype=int)
        hold_used = np.full(entry_idx.shape[0], max(1, hold_bars), dtype=int)

    exit_idx = entry_idx + hold_used
    valid = exit_idx < n
    entry_idx, exit_idx = entry_idx[valid], exit_idx[valid]
    
    if entry_idx.size == 0:
        return {"samples": float(fold.samples), "trade_count": 0.0, "cum_return": 0.0, "long_only_cum_return": float(fold.buy_hold_return)}, np.array([], dtype=float)

    realized = (fold.close[exit_idx] / fold.close[entry_idx]) - 1.0
    position = signal[entry_idx]
    tx_cost = np.where(position != 0, 2.0 * cost_rate, 0.0)
    strategy = position * realized - tx_cost
    executed = strategy[position != 0]

    trade_dir_acc = float(np.mean(np.sign(position[position != 0]) == np.sign(realized[position != 0]))) if np.any(position != 0) else 0.0
    
    metrics = {
        "samples": float(fold.samples),
        "trade_count": float(executed.size),
        "cum_return": _cum_return_np(executed),
        "long_only_cum_return": float(fold.buy_hold_return),
        "sharpe": _safe_sharpe_np(executed, periods_per_year),
        "max_drawdown": _max_drawdown_np(executed),
        "win_rate": float(np.mean(executed > 0)) if executed.size > 0 else 0.0,
        "avg_trade_return": float(np.mean(executed)) if executed.size > 0 else 0.0,
        "directional_accuracy_all": float(fold.directional_accuracy),
        "directional_accuracy_trades": trade_dir_acc,
        "directional_baseline_all": max(fold.up_ratio, 1.0 - fold.up_ratio),
        "exposure": float(executed.size / max(1, fold.samples)),
    }
    return metrics, executed


def _evaluate_summary_from_cache(
    fold_cache: List[FoldCache],
    threshold: float,
    hold_bars: int,
    cost_bps: float,
    dynamic_hold: bool,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], float]:
    """전체 폴드 캐시를 순회하며 통합 성과 요약을 산출합니다."""
    periods_per_year = max(1, int((252 * 390) / max(1, hold_bars)))
    cost_rate = cost_bps / 10_000.0

    folds, executed_list = [], []
    total_samples, up_count, dir_hit, trade_dir_hit, total_trades = 0, 0.0, 0.0, 0.0, 0
    bh_factors = []

    for fold in fold_cache:
        fm, executed = _evaluate_fold_from_cache(fold, threshold, hold_bars, cost_rate, dynamic_hold, periods_per_year)
        fm["fold"] = float(fold.fold)
        folds.append(fm)
        executed_list.append(executed)
        total_samples += fold.samples
        total_trades += int(fm["trade_count"])
        up_count += fold.up_ratio * fold.samples
        dir_hit += fold.directional_accuracy * fold.samples
        trade_dir_hit += fm.get("directional_accuracy_trades", 0.0) * max(1.0, fm["trade_count"])
        bh_factors.append(1.0 + fold.buy_hold_return)

    executed_all = np.concatenate([x for x in executed_list if x.size > 0]) if any(x.size > 0 for x in executed_list) else np.array([], dtype=float)
    up_ratio_all = float(up_count / max(1, total_samples))
    long_only_cum = float(np.prod(bh_factors) - 1.0) if bh_factors else 0.0
    cum_return = _cum_return_np(executed_all)

    summary = {
        "samples": float(total_samples),
        "trade_count": float(total_trades),
        "cum_return": cum_return,
        "long_only_cum_return": long_only_cum,
        "alpha_vs_long_only": cum_return - long_only_cum,
        "sharpe": _safe_sharpe_np(executed_all, periods_per_year),
        "max_drawdown": _max_drawdown_np(executed_all),
        "win_rate": float(np.mean(executed_all > 0)) if executed_all.size > 0 else 0.0,
        "avg_trade_return": float(np.mean(executed_all)) if executed_all.size > 0 else 0.0,
        "directional_accuracy_all": float(dir_hit / max(1, total_samples)),
        "directional_accuracy_trades": float(trade_dir_hit / max(1, total_trades)),
        "directional_baseline_all": max(up_ratio_all, 1.0 - up_ratio_all),
        "exposure": float(total_trades / max(1, total_samples)),
    }
    min_trades = min((f.get("trade_count", 0.0) for f in folds), default=0.0)
    return summary, folds, float(min_trades)


# --- Main Public API ---

def run_walkforward_backtest(
    feat_df: pd.DataFrame,
    feature_cols: Optional[List[str]] = None,
    model_type: str = "ensemble",
    train_rows: int = 80_000,
    test_rows: int = 2_000,
    step_rows: int = 2_000,
    cost_bps: float = 1.0,
    hold_bars: int = 5,
    threshold_override: Optional[float] = None,
    dynamic_hold: bool = False,
    pretrained_artifact: Optional[LinearModelArtifact] = None,
) -> BacktestResult:
    """워크포워드(Rolling window) 방식의 백테스트를 수행합니다."""
    if feat_df.empty: raise ValueError("데이터가 없습니다.")
    
    modeler = TimeSeriesModeler()
    feature_cols = feature_cols or [c for c in modeler.DEFAULT_FEATURES if c in feat_df.columns]
    
    cost_rate = cost_bps / 10_000.0
    periods_per_year = max(1, int((252 * 390) / max(1, hold_bars)))

    folds, detail_frames, signal_frames, bh_returns = [], [], [], []
    start, n, fold_idx = 0, len(feat_df), 0

    while start + train_rows + test_rows <= n:
        train_df = feat_df.iloc[start : start + train_rows].copy()
        test_df = feat_df.iloc[start + train_rows : start + train_rows + test_rows].copy()

        pred, threshold = _fit_predict_fold_model(train_df, test_df, feature_cols, model_type, cost_bps, pretrained_artifact)
        if threshold_override is not None: threshold = float(threshold_override)
        
        out = test_df[["ts", "close", "target_return"]].copy().reset_index(drop=True)
        if "rv_30" in test_df.columns: out["rv_30"] = test_df["rv_30"].to_numpy()
        out["fold"], out["pred_return"], out["threshold"] = fold_idx, pred, threshold
        out["signal"] = np.where(pred > threshold, 1, np.where(pred < -threshold, -1, 0))

        dynamic_holds = None
        if dynamic_hold:
            vol = out["rv_30"].dropna()
            if not vol.empty:
                p25, p75 = vol.quantile([0.25, 0.75]).values
                dynamic_holds = out["rv_30"].apply(lambda rv: max(3, hold_bars-2) if rv > p75 else min(15, hold_bars+3) if rv < p25 else hold_bars).astype(int).to_numpy()
            else: dynamic_holds = np.full(len(out), hold_bars, dtype=int)
            trade_idx = _build_trade_index(dynamic_holds)
        else:
            trade_idx = np.arange(0, len(out), max(1, hold_bars))

        # Build trades and collect metrics
        close_arr = out["close"].to_numpy()
        entry_idx = trade_idx[trade_idx + (dynamic_holds[trade_idx] if dynamic_hold else hold_bars) < len(out)]
        hold_used = dynamic_holds[entry_idx] if dynamic_hold else np.full(entry_idx.size, hold_bars)
        exit_idx = entry_idx + hold_used
        
        realized = (close_arr[exit_idx] / close_arr[entry_idx]) - 1.0
        pos = out["signal"].to_numpy()[entry_idx]
        tx = np.where(pos != 0, 2.0 * cost_rate, 0.0)
        strat = pos * realized - tx
        
        trade_df = pd.DataFrame({"ts": out["ts"].iloc[entry_idx], "strategy_return": strat, "is_trade": (pos != 0).astype(int)})
        bh_val = (close_arr[-1]/close_arr[0]-1.0) if close_arr[0]>0 else 0.0
        bh_returns.append(bh_val)
        
        executed = trade_df[trade_df["is_trade"] == 1].copy()
        fm = _calc_metrics(out, executed, periods_per_year, buy_hold_return=bh_val)
        fm["fold"] = float(fold_idx)
        folds.append(fm)
        detail_frames.append(trade_df)
        signal_frames.append(out)

        fold_idx += 1
        start += step_rows

    if not detail_frames: raise ValueError("폴드가 생성되지 않았습니다.")
    
    detail = pd.concat(detail_frames, ignore_index=True)
    all_signals = pd.concat(signal_frames, ignore_index=True)
    summary_bh = float(np.prod([1.0 + r for r in bh_returns]) - 1.0)
    summary = _calc_metrics(all_signals, detail[detail["is_trade"] == 1], periods_per_year, buy_hold_return=summary_bh)
    summary.update({"fold_count": len(folds), "train_rows": train_rows, "test_rows": test_rows, "step_rows": step_rows, "cost_bps": cost_bps, "hold_bars": hold_bars, "dynamic_hold": int(dynamic_hold), "model_type": model_type})
    
    return BacktestResult(summary=summary, folds=folds, detail=detail)


def _calculate_adaptive_threshold_grid(fold_cache: List[FoldCache], multipliers: np.ndarray) -> Tuple[np.ndarray, float]:
    """모든 폴드의 변동성 중위값을 기준으로 적응형 임계값 그리드를 생성합니다."""
    median_vol = float(np.median([fc.baseline_volatility for fc in fold_cache]))
    grid = np.unique(np.round(multipliers * median_vol, 6))
    grid = grid[grid >= 1e-5] # 필터링
    if grid.size == 0: grid = np.array([0.0001, 0.0003, 0.0005])
    return grid, median_vol


def run_parameter_optimization(
    feat_df: pd.DataFrame,
    feature_cols: Optional[List[str]] = None,
    model_type: str = "ensemble",
    train_rows: int = 80_000,
    test_rows: int = 2_000,
    step_rows: int = 2_000,
    dynamic_hold: bool = False,
    pretrained_artifact: Optional[LinearModelArtifact] = None,
) -> pd.DataFrame:
    """그리드 서치를 통해 최적의 거래 파라미터를 탐색합니다."""
    vol_multiplier_grid = np.array([0.15, 0.25, 0.4, 0.6, 0.8, 1.0, 1.5, 2.0], dtype=float)
    hold_bars_grid = [2, 3, 5, 7, 10, 15]
    cost_bps_grid = [0.8, 1.0, 1.5, 2.0, 2.5, 3.0]

    feature_cols = feature_cols or [c for c in TimeSeriesModeler().DEFAULT_FEATURES if c in feat_df.columns]
    
    # 1. Fold Cache 준비 (모델 학습 1회)
    fold_cache = []
    start, n, fold_idx = 0, len(feat_df), 0
    while start + train_rows + test_rows <= n:
        train_df = feat_df.iloc[start : start + train_rows]
        test_df = feat_df.iloc[start + train_rows : start + train_rows + test_rows]
        pred, _ = _fit_predict_fold_model(train_df, test_df, feature_cols, model_type, 1.0, pretrained_artifact)
        
        target = test_df["target_return"].to_numpy()
        close = test_df["close"].to_numpy()
        rv = test_df["rv_30"].to_numpy() if "rv_30" in test_df.columns else None
        
        train_target = train_df["target_return"].to_numpy()
        base_vol = float(np.std(train_target)) if train_target.size > 0 else 0.001
        
        rv_p25, rv_p75 = None, None
        if rv is not None:
            valid = rv[~np.isnan(rv)]
            if valid.size > 0: rv_p25, rv_p75 = float(np.quantile(valid, 0.25)), float(np.quantile(valid, 0.75))
            
        fold_cache.append(FoldCache(fold_idx, pred, target, close, rv, len(target), float(np.mean(target>0)), float(np.mean(np.sign(pred)==np.sign(target))), float(close[-1]/close[0]-1.0), rv_p25, rv_p75, base_vol))
        start += step_rows; fold_idx += 1

    # 2. Adaptive Threshold 그리드 생성
    threshold_grid, median_vol = _calculate_adaptive_threshold_grid(fold_cache, vol_multiplier_grid)
    logger.info(f"Adaptive Grid: median_vol={median_vol:.6f}, grid={threshold_grid}")

    # 3. Grid Search
    results, progress, n_total = [], 0, len(threshold_grid) * len(hold_bars_grid) * len(cost_bps_grid)
    for t in threshold_grid:
        for h in hold_bars_grid:
            for c in cost_bps_grid:
                progress += 1
                summary, folds, min_trades = _evaluate_summary_from_cache(fold_cache, float(t), int(h), float(c), dynamic_hold)
                
                results.append({
                    "threshold": float(t), "vol_scale": float(t/median_vol) if median_vol > 1e-8 else 0,
                    "baseline_vol": median_vol, "hold_bars": float(h), "cost_bps": float(c),
                    "cum_return": float(summary["cum_return"]), "sharpe": float(summary["sharpe"]),
                    "max_dd": float(summary["max_drawdown"]), "win_rate": float(summary["win_rate"]),
                    "alpha": float(summary["alpha_vs_long_only"]), "trade_count": float(summary["trade_count"]),
                    "min_trades_in_fold": float(min_trades), "dir_acc": float(summary["directional_accuracy_all"]),
                    "dir_acc_trades": float(summary["directional_accuracy_trades"]),
                    "dir_baseline": float(summary["directional_baseline_all"]),
                    "avg_trade_return": float(summary["avg_trade_return"])
                })
                if progress % 50 == 0: logger.info(f"Progress: {progress}/{n_total}")

    return pd.DataFrame(results)


def recommend_parameters(opt_results: pd.DataFrame) -> Dict[str, Any]:
    """최적화 결과 중 가장 견고한(Robust) 성과를 내는 파라미터를 추천합니다."""
    if opt_results.empty: raise ValueError("결과 데이터 없음")
    
    scored = opt_results.copy()
    scored["robust_score"] = (
        (1.5 * scored["dir_acc"]) + (1.2 * scored["dir_acc_trades"]) + (0.8 * scored["win_rate"])
        + (0.5 * np.clip(scored["alpha"], -0.1, 0.1)) - (0.3 * np.abs(scored["max_dd"]))
        - (0.5 * np.where(scored["hold_bars"] < 5, 1.0, 0.0))
    )

    # 필터링 조건(강→중→약 순으로 적용; 저표본 파라미터를 최종 선택에서 배제)
    strict = scored[
        (scored["min_trades_in_fold"] >= 10)
        & (scored["trade_count"] >= 500)
        & (scored["hold_bars"] >= 5)
        & (scored["dir_acc_trades"] >= 0.52)
    ]
    medium = scored[
        (scored["min_trades_in_fold"] >= 5)
        & (scored["trade_count"] >= 200)
        & (scored["hold_bars"] >= 5)
        & (scored["dir_acc_trades"] >= 0.50)
    ]
    loose = scored[
        (scored["min_trades_in_fold"] >= 2)
        & (scored["trade_count"] >= 50)
        & (scored["hold_bars"] >= 3)
    ]

    if not strict.empty:
        candidates = strict
        selection_tier = "strict"
    elif not medium.empty:
        candidates = medium
        selection_tier = "medium"
    elif not loose.empty:
        candidates = loose
        selection_tier = "loose"
    else:
        # 최후 fallback도 거래 수를 우선시해 극단적 저표본 선택을 줄임
        candidates = scored.sort_values(by=["trade_count", "robust_score"], ascending=False).head(30)
        selection_tier = "fallback"
    filter_applied = selection_tier != "fallback"
    
    top = candidates.sort_values(by=["dir_acc_trades", "robust_score"], ascending=False).head(5)
    best = top.iloc[0]
    
    res = {
        "best_params": {"threshold": float(best["threshold"]), "hold_bars": int(best["hold_bars"]), "cost_bps": float(best["cost_bps"]), 
                       "vol_scale": round(float(best.get("vol_scale", 0)), 4), "baseline_vol": round(float(best.get("baseline_vol",0)), 6)},
        "top5": top.to_dict(orient="records"),
        "recommendation_reason": {"dir_acc": float(best["dir_acc"]), "dir_acc_trades": float(best["dir_acc_trades"]), 
                                 "filter_applied": filter_applied, "selection_tier": selection_tier,
                                 "baseline_volatility": float(best.get("baseline_vol", 0))}
    }
    return res
