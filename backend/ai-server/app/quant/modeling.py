import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.preprocessing import RobustScaler

from app.quant.feature_selector import FeatureValiditySelector

# --- Optional Machine Learning Frameworks ---
try:
    from lightgbm import Booster as LGBBooster
    from lightgbm import LGBMRegressor
except ImportError:
    LGBBooster = None
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


def _enabled_ensemble_models() -> set[str]:
    raw = os.getenv("QUANT_ENSEMBLE_MODELS", "lightgbm,xgboost,catboost")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _feature_selection_enabled() -> bool:
    return os.getenv("QUANT_ENABLE_FEATURE_SELECTION", "1").strip().lower() not in {"0", "false", "no", "off"}


def _feature_selection_top_k() -> int:
    return max(5, int(os.getenv("QUANT_FEATURE_TOP_K", "18")))


def _feature_selection_min_features() -> int:
    return max(5, int(os.getenv("QUANT_FEATURE_MIN_COUNT", "8")))


def optimize_threshold_profitability(y_true: np.ndarray, y_pred: np.ndarray, cost_bps: float) -> float:
    """훈련 예측값 기준으로 거래비용 차감 후 수익이 최대가 되는 임계값을 선택합니다."""
    cand = np.linspace(0.0, float(np.std(y_pred)) if np.std(y_pred) > 0 else 0.001, 40)
    best_t = 0.0
    best_profit = -np.inf
    cost = 2.0 * (cost_bps / 10000.0)
    for t in cand:
        signal = np.where(y_pred > t, 1, np.where(y_pred < -t, -1, 0))
        mask = signal != 0
        if not np.any(mask):
            continue
        profit = float(np.sum(signal[mask] * y_true[mask]) - (np.sum(mask) * cost))
        if profit > best_profit:
            best_profit = profit
            best_t = float(t)
    return best_t


@dataclass
class LinearModelArtifact:
    """학습된 모델의 가중치, 메타데이터, 성능 지표를 담는 아티팩트 클래스"""
    feature_names: List[str]
    coefficients: List[float]
    intercept: float
    threshold: float
    metrics: Dict[str, Any]
    model_type: str = "linear"
    ensemble_weights: Optional[Dict[str, float]] = None
    model_files: Optional[Dict[str, str]] = None
    available_models: Optional[List[str]] = None
    feature_importances: Optional[Dict[str, float]] = None
    scaler_center: Optional[List[float]] = None
    scaler_scale: Optional[List[float]] = None
    input_feature_names: Optional[List[str]] = None
    pca_groups: Optional[Dict[str, List[str]]] = None
    pca_components: Optional[Dict[str, List[float]]] = None
    pca_means: Optional[Dict[str, List[float]]] = None
    pca_explained_variance: Optional[Dict[str, float]] = None
    _runtime_models: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """아티팩트를 JSON 저장 전용 딕셔너리로 변환합니다."""
        return {
            "model_type": self.model_type,
            "feature_names": self.feature_names,
            "coefficients": self.coefficients,
            "intercept": self.intercept,
            "threshold": self.threshold,
            "metrics": self.metrics,
            "ensemble_weights": self.ensemble_weights or {},
            "model_files": self.model_files or {},
            "available_models": self.available_models or [],
            "feature_importances": self.feature_importances or {},
            "scaler_center": self.scaler_center or [],
            "scaler_scale": self.scaler_scale or [],
            "input_feature_names": self.input_feature_names or self.feature_names,
            "pca_groups": self.pca_groups or {},
            "pca_components": self.pca_components or {},
            "pca_means": self.pca_means or {},
            "pca_explained_variance": self.pca_explained_variance or {},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LinearModelArtifact":
        """딕셔너리로부터 아티팩트 객체를 생성합니다."""
        return cls(
            model_type=data.get("model_type", "linear"),
            feature_names=data["feature_names"],
            coefficients=data.get("coefficients", []),
            intercept=float(data.get("intercept", 0.0)),
            threshold=float(data["threshold"]),
            metrics=data.get("metrics", {}),
            ensemble_weights=data.get("ensemble_weights"),
            model_files=data.get("model_files"),
            available_models=data.get("available_models"),
            feature_importances=data.get("feature_importances"),
            scaler_center=data.get("scaler_center"),
            scaler_scale=data.get("scaler_scale"),
            input_feature_names=data.get("input_feature_names"),
            pca_groups=data.get("pca_groups"),
            pca_components=data.get("pca_components"),
            pca_means=data.get("pca_means"),
            pca_explained_variance=data.get("pca_explained_variance"),
        )


class TimeSeriesModeler:
    """시계열 주가 데이터를 위한 모델 학습 및 예측을 담당하는 클래스"""
    
    # 모델 학습에 사용하는 기본 피처 목록
    DEFAULT_FEATURES = [
        "ret_1m", "mom_5", "mom_15", "vol_5", "vol_20", 
        "macd", "macd_signal", "macd_hist", "bb_width", "bb_pct_b", 
        "rsi_14", "dist_vwap", "volume_z20", "rv_30", "skew_30", 
        "session_progress", "close_high_ratio", "close_low_ratio", 
        "price_accel", "is_market_open_30", "is_market_close_30",
        "mom_vol_interaction", "rsi_momentum_cross"
    ]

    ENHANCED_EXTRA_FEATURES = [
        "mtf_15m_rsi_14",
        "mtf_15m_trend",
        "mtf_60m_rsi_14",
        "mtf_60m_trend",
        "mtf_1d_rsi_14",
        "mtf_1d_trend",
    ]

    GROUPED_PCA_GROUPS = {
        "trend_score": ["sma_5", "sma_20", "ema_12", "ema_26", "vwap"],
    }

    def __init__(self, model_type: str = "ensemble", feature_profile: str = "baseline"):
        self.model_type = model_type
        self.feature_profile = feature_profile

    def get_feature_columns(self, feat_df: pd.DataFrame) -> List[str]:
        if self.feature_profile in {"mtf", "enhanced"}:
            ordered = self.DEFAULT_FEATURES + self.ENHANCED_EXTRA_FEATURES + [
                "sma_5", "sma_20", "ema_12", "ema_26", "vwap"
            ]
        else:
            ordered = self.DEFAULT_FEATURES
        return [c for c in ordered if c in feat_df.columns]

    def select_feature_columns(self, feat_df: pd.DataFrame, feature_cols: List[str]) -> List[str]:
        if not _feature_selection_enabled() or len(feature_cols) <= _feature_selection_min_features():
            return feature_cols
        if feat_df.empty or "target_return" not in feat_df.columns or "ts" not in feat_df.columns:
            return feature_cols

        try:
            selector = FeatureValiditySelector(max_pair_corr=0.92)
            candidate_df = feat_df[["ts", "target_return"] + feature_cols].copy()
            result = selector.select(candidate_df, top_k=_feature_selection_top_k())
            selected = [c for c in feature_cols if c in result.selected_features]
            if len(selected) < _feature_selection_min_features():
                return feature_cols
            logger.info(
                "feature selection applied | profile=%s | original=%d | selected=%d",
                self.feature_profile,
                len(feature_cols),
                len(selected),
            )
            return selected
        except Exception as exc:
            logger.warning("feature selection skipped due to error: %s", exc)
            return feature_cols

    def _prepare_xy(self, df: pd.DataFrame, feature_cols: List[str]) -> Tuple[np.ndarray, np.ndarray]:
        """피처와 타겟 변수를 Numpy 배열로 변환합니다."""
        x = df[feature_cols].astype(float).to_numpy()
        y = df["target_return"].astype(float).to_numpy()
        return x, y

    def _fit_feature_transform(
        self,
        train_df: pd.DataFrame,
        feature_cols: List[str],
    ) -> Tuple[RobustScaler, Dict[str, Any], np.ndarray]:
        x_train_raw = train_df[feature_cols].astype(float).to_numpy()
        scaler = RobustScaler()
        scaler.fit(x_train_raw)
        x_train_scaled = scaler.transform(x_train_raw)

        transform_meta: Dict[str, Any] = {
            "input_feature_names": list(feature_cols),
            "feature_names": list(feature_cols),
            "pca_groups": {},
            "pca_components": {},
            "pca_means": {},
            "pca_explained_variance": {},
            "passthrough_features": list(feature_cols),
        }
        if self.feature_profile != "enhanced":
            return scaler, transform_meta, x_train_scaled

        grouped_features = []
        used_features = set()
        group_scores: List[np.ndarray] = []

        for group_name, group_cols in self.GROUPED_PCA_GROUPS.items():
            available = [c for c in group_cols if c in feature_cols]
            if len(available) < 2:
                continue
            idxs = [feature_cols.index(c) for c in available]
            subset = x_train_scaled[:, idxs]
            pca = PCA(n_components=1, random_state=42)
            score = pca.fit_transform(subset).reshape(-1)
            group_scores.append(score)
            grouped_features.append(group_name)
            used_features.update(available)
            transform_meta["pca_groups"][group_name] = available
            transform_meta["pca_components"][group_name] = pca.components_[0].astype(float).tolist()
            transform_meta["pca_means"][group_name] = pca.mean_.astype(float).tolist()
            transform_meta["pca_explained_variance"][group_name] = float(pca.explained_variance_ratio_[0])

        passthrough = [c for c in feature_cols if c not in used_features]
        passthrough_idxs = [feature_cols.index(c) for c in passthrough]
        x_passthrough = x_train_scaled[:, passthrough_idxs] if passthrough_idxs else np.empty((len(train_df), 0))
        x_group = np.column_stack(group_scores) if group_scores else np.empty((len(train_df), 0))
        transform_meta["passthrough_features"] = passthrough
        transform_meta["feature_names"] = passthrough + grouped_features
        return scaler, transform_meta, np.hstack([x_passthrough, x_group])

    def _transform_with_meta(
        self,
        df: pd.DataFrame,
        scaler: Optional[RobustScaler] = None,
        scaler_center: Optional[List[float]] = None,
        scaler_scale: Optional[List[float]] = None,
        transform_meta: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        if transform_meta is None:
            raise ValueError("transform_meta가 필요합니다.")
        input_features = transform_meta.get("input_feature_names") or transform_meta.get("feature_names") or []
        if not input_features:
            raise ValueError("입력 피처 목록이 비어 있습니다.")
        x_raw = df[input_features].astype(float).to_numpy()

        if scaler is not None:
            x_scaled = scaler.transform(x_raw)
        else:
            center = np.array(scaler_center or [], dtype=float)
            scale = np.array(scaler_scale or [], dtype=float)
            if center.size != x_raw.shape[1] or scale.size != x_raw.shape[1]:
                raise ValueError("저장된 scaler 메타데이터와 입력 피처 수가 일치하지 않습니다.")
            safe_scale = np.where(np.abs(scale) > 1e-12, scale, 1.0)
            x_scaled = (x_raw - center) / safe_scale

        passthrough = transform_meta.get("passthrough_features", input_features)
        passthrough_idxs = [input_features.index(c) for c in passthrough]
        x_passthrough = x_scaled[:, passthrough_idxs] if passthrough_idxs else np.empty((len(df), 0))

        pca_groups = transform_meta.get("pca_groups", {})
        pca_components = transform_meta.get("pca_components", {})
        pca_means = transform_meta.get("pca_means", {})
        group_scores: List[np.ndarray] = []
        for group_name in pca_groups:
            cols = pca_groups[group_name]
            idxs = [input_features.index(c) for c in cols]
            subset = x_scaled[:, idxs]
            mean = np.array(pca_means[group_name], dtype=float)
            comp = np.array(pca_components[group_name], dtype=float)
            group_scores.append(((subset - mean) @ comp).reshape(-1))

        x_group = np.column_stack(group_scores) if group_scores else np.empty((len(df), 0))
        return np.hstack([x_passthrough, x_group])

    @staticmethod
    def build_transform_meta_from_artifact(
        artifact: LinearModelArtifact,
        feature_cols: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        input_features = artifact.input_feature_names or feature_cols or artifact.feature_names
        grouped_inputs = {c for cols in (artifact.pca_groups or {}).values() for c in cols}
        return {
            "input_feature_names": input_features,
            "feature_names": artifact.feature_names,
            "pca_groups": artifact.pca_groups or {},
            "pca_components": artifact.pca_components or {},
            "pca_means": artifact.pca_means or {},
            "passthrough_features": [c for c in input_features if c not in grouped_inputs],
        }

    def transform_with_artifact(
        self,
        df: pd.DataFrame,
        artifact: LinearModelArtifact,
        feature_cols: Optional[List[str]] = None,
    ) -> np.ndarray:
        transform_meta = self.build_transform_meta_from_artifact(artifact, feature_cols)
        return self._transform_with_meta(
            df,
            scaler_center=artifact.scaler_center,
            scaler_scale=artifact.scaler_scale,
            transform_meta=transform_meta,
        )

    def predict_with_artifact(
        self,
        df: pd.DataFrame,
        artifact: LinearModelArtifact,
        feature_cols: Optional[List[str]] = None,
    ) -> np.ndarray:
        x = self.transform_with_artifact(df, artifact, feature_cols)
        if artifact.model_type == "ensemble":
            if not artifact._runtime_models:
                raise RuntimeError("모델이 로드되지 않았습니다.")
            weights = artifact.ensemble_weights or {}
            pred = np.zeros(x.shape[0], dtype=float)
            for name, model in artifact._runtime_models.items():
                pred += weights.get(name, 0.0) * self._predict_safe(model, x, artifact.feature_names)
            return pred

        coeffs = np.array(artifact.coefficients, dtype=float)
        return x @ coeffs + artifact.intercept

    def fit_predict_for_split(
        self,
        train_df: pd.DataFrame,
        test_df: pd.DataFrame,
        feature_cols: Optional[List[str]] = None,
        cost_bps: float = 1.0,
        pretrained_artifact: Optional[LinearModelArtifact] = None,
    ) -> Tuple[np.ndarray, float]:
        feature_cols = feature_cols or self.get_feature_columns(train_df)
        y_train = train_df["target_return"].astype(float).to_numpy()

        if pretrained_artifact is not None and pretrained_artifact._runtime_models:
            pred = self.predict_with_artifact(test_df, pretrained_artifact, feature_cols=feature_cols)
            pred_train = self.predict_with_artifact(train_df, pretrained_artifact, feature_cols=feature_cols)
            threshold = optimize_threshold_profitability(y_train, pred_train, cost_bps)
            return pred, threshold

        selected_feature_cols = self.select_feature_columns(train_df, feature_cols)
        scaler, transform_meta, x_train = self._fit_feature_transform(train_df, selected_feature_cols)
        x_test = self._transform_with_meta(test_df, scaler=scaler, transform_meta=transform_meta)
        transformed_features = transform_meta["feature_names"]

        if self.model_type == "linear":
            x_train_aug = np.hstack([x_train, np.ones((x_train.shape[0], 1))])
            coeffs_aug, *_ = np.linalg.lstsq(x_train_aug, y_train, rcond=None)
            pred = x_test @ coeffs_aug[:-1] + coeffs_aug[-1]
            pred_train = x_train @ coeffs_aug[:-1] + coeffs_aug[-1]
            threshold = optimize_threshold_profitability(y_train, pred_train, cost_bps)
            return pred, threshold

        preds: Dict[str, np.ndarray] = {}
        tr_preds: Dict[str, np.ndarray] = {}
        enabled_models = _enabled_ensemble_models()

        if LGBMRegressor is not None and "lightgbm" in enabled_models:
            lgbm = LGBMRegressor(n_estimators=100, learning_rate=0.05, verbose=-1, random_state=42)
            lgbm.fit(x_train, y_train)
            preds["lightgbm"] = self._predict_safe(lgbm, x_test, transformed_features)
            tr_preds["lightgbm"] = self._predict_safe(lgbm, x_train, transformed_features)

        if XGBRegressor is not None and "xgboost" in enabled_models:
            xgb = XGBRegressor(n_estimators=120, learning_rate=0.05, verbosity=0, random_state=42)
            xgb.fit(x_train, y_train)
            preds["xgboost"] = self._predict_safe(xgb, x_test, transformed_features)
            tr_preds["xgboost"] = self._predict_safe(xgb, x_train, transformed_features)

        if CatBoostRegressor is not None and "catboost" in enabled_models:
            cat = CatBoostRegressor(iterations=140, learning_rate=0.05, verbose=False, random_seed=42)
            cat.fit(x_train, y_train)
            preds["catboost"] = self._predict_safe(cat, x_test, transformed_features)
            tr_preds["catboost"] = self._predict_safe(cat, x_train, transformed_features)

        if not preds:
            x_train_aug = np.hstack([x_train, np.ones((x_train.shape[0], 1))])
            coeffs_aug, *_ = np.linalg.lstsq(x_train_aug, y_train, rcond=None)
            pred = x_test @ coeffs_aug[:-1] + coeffs_aug[-1]
            pred_train = x_train @ coeffs_aug[:-1] + coeffs_aug[-1]
            threshold = optimize_threshold_profitability(y_train, pred_train, cost_bps)
            return pred, threshold

        up_ratio = float(np.mean(y_train > 0))
        baseline = max(up_ratio, 1.0 - up_ratio)
        raw_scores = {}
        for name, p in tr_preds.items():
            dir_acc = float(np.mean(np.sign(p) == np.sign(y_train)))
            raw_scores[name] = max(1e-6, 0.7 * dir_acc + 0.3 * max(dir_acc - baseline, 0))

        score_sum = sum(raw_scores.values())
        pred = sum((raw_scores[name] / score_sum) * p for name, p in preds.items())
        pred_train = sum((raw_scores[name] / score_sum) * p for name, p in tr_preds.items())
        threshold = optimize_threshold_profitability(y_train, pred_train, cost_bps)
        return pred, threshold

    def train(self, feat_df: pd.DataFrame, feature_cols: Optional[List[str]] = None) -> LinearModelArtifact:
        """지정된 모드(linear/ensemble)에 따라 모델을 학습합니다."""
        feature_cols = feature_cols or self.get_feature_columns(feat_df)
        
        # Train/Test Time-series split (보수적인 8:2 분할)
        split_idx = int(len(feat_df) * 0.8)
        train_df = feat_df.iloc[:split_idx]
        test_df = feat_df.iloc[split_idx:]
        selected_feature_cols = self.select_feature_columns(train_df, feature_cols)

        y_tr = train_df["target_return"].astype(float).to_numpy()
        y_te = test_df["target_return"].astype(float).to_numpy()
        scaler, transform_meta, x_tr_scaled = self._fit_feature_transform(train_df, selected_feature_cols)
        x_te_scaled = self._transform_with_meta(test_df, scaler=scaler, transform_meta=transform_meta)

        if self.model_type == "linear":
            return self._train_linear(x_tr_scaled, y_tr, x_te_scaled, y_te, selected_feature_cols, scaler, transform_meta)
        return self._train_ensemble(x_tr_scaled, y_tr, x_te_scaled, y_te, selected_feature_cols, scaler, transform_meta)

    def _train_linear(self, x_tr, y_tr, x_te, y_te, features, scaler, transform_meta) -> LinearModelArtifact:
        """선형 회귀 알고리즘을 사용하여 모델을 학습합니다."""
        x_tr_aug = np.hstack([x_tr, np.ones((x_tr.shape[0], 1))])
        coeffs_aug, *_ = np.linalg.lstsq(x_tr_aug, y_tr, rcond=None)
        coeffs, intercept = coeffs_aug[:-1], float(coeffs_aug[-1])
        
        pred = x_te @ coeffs + intercept
        mse = float(np.mean((pred - y_te) ** 2))
        dir_acc = float(np.mean(np.sign(pred) == np.sign(y_te)))
        
        return LinearModelArtifact(
            feature_names=transform_meta["feature_names"], coefficients=coeffs.tolist(), intercept=intercept,
            threshold=float(np.std(y_tr)*0.25),
            metrics={"mse": mse, "directional_accuracy": dir_acc},
            scaler_center=scaler.center_.tolist(), scaler_scale=scaler.scale_.tolist(),
            input_feature_names=features,
            pca_groups=transform_meta["pca_groups"],
            pca_components=transform_meta["pca_components"],
            pca_means=transform_meta["pca_means"],
            pca_explained_variance=transform_meta["pca_explained_variance"],
        )

    def _merge_feature_importances(self, models, weights, features) -> Dict[str, float]:
        agg = np.zeros(len(features), dtype=float)
        for name, m in models.items():
            if hasattr(m, "feature_importances_"): imp = np.array(m.feature_importances_)
            elif hasattr(m, "get_feature_importance"): imp = np.array(m.get_feature_importance())
            else: continue
            if imp.sum() > 0: imp = imp / imp.sum()
            agg += weights.get(name, 0.0) * imp
        if agg.sum() > 0: agg = agg / agg.sum()
        return {features[i]: float(agg[i]) for i in range(len(features))}

    @staticmethod
    def _predict_safe(model: Any, x: np.ndarray, feature_names: List[str]) -> np.ndarray:
        """
        sklearn 래퍼 모델이 feature_names_in_를 가진 경우 DataFrame으로 맞춰 경고를 방지합니다.
        기존 numpy 입력 경로와 결과는 동일합니다.
        """
        try:
            names_in = getattr(model, "feature_names_in_", None)
            if names_in is not None and len(names_in) == x.shape[1]:
                return model.predict(pd.DataFrame(x, columns=list(names_in)))
        except Exception:
            pass
        return model.predict(x)

    def _train_ensemble(self, x_tr, y_tr, x_te, y_te, features, scaler, transform_meta) -> LinearModelArtifact:
        """LightGBM, XGBoost, CatBoost의 성능 가중치 기반 앙상블 모델을 학습합니다."""
        models, test_preds, tr_preds = {}, {}, {}
        
        enabled_models = _enabled_ensemble_models()

        if LGBMRegressor and "lightgbm" in enabled_models:
            m = LGBMRegressor(n_estimators=120, learning_rate=0.05, verbose=-1, random_state=42)
            m.fit(x_tr, y_tr)
            models["lightgbm"] = m
            test_preds["lightgbm"] = self._predict_safe(m, x_te, transform_meta["feature_names"])
            tr_preds["lightgbm"] = self._predict_safe(m, x_tr, transform_meta["feature_names"])
        
        if XGBRegressor and "xgboost" in enabled_models:
            m = XGBRegressor(n_estimators=140, learning_rate=0.05, verbosity=0, random_state=42)
            m.fit(x_tr, y_tr)
            models["xgboost"] = m
            test_preds["xgboost"] = self._predict_safe(m, x_te, transform_meta["feature_names"])
            tr_preds["xgboost"] = self._predict_safe(m, x_tr, transform_meta["feature_names"])

        if CatBoostRegressor and "catboost" in enabled_models:
            m = CatBoostRegressor(iterations=160, learning_rate=0.05, verbose=False, random_seed=42)
            m.fit(x_tr, y_tr)
            models["catboost"] = m
            test_preds["catboost"] = self._predict_safe(m, x_te, transform_meta["feature_names"])
            tr_preds["catboost"] = self._predict_safe(m, x_tr, transform_meta["feature_names"])

        if not models: return self._train_linear(x_tr, y_tr, x_te, y_te, features, scaler, transform_meta)

        # 성능 기반 가중치 계산
        up_ratio = float(np.mean(y_te > 0))
        baseline = max(up_ratio, 1.0 - up_ratio)
        weights = {}
        for name, p in test_preds.items():
            acc = float(np.mean(np.sign(p) == np.sign(y_te)))
            weights[name] = max(1e-6, acc)
        
        total_w = sum(weights.values())
        weights = {k: v / total_w for k, v in weights.items()}
        
        ens_pred = sum(weights[k] * test_preds[k] for k in models)
        mse = float(np.mean((ens_pred - y_te)**2))
        dir_acc = float(np.mean(np.sign(ens_pred) == np.sign(y_te)))

        return LinearModelArtifact(
            model_type="ensemble", feature_names=transform_meta["feature_names"], coefficients=[], intercept=0.0,
            threshold=float(np.percentile(np.abs(ens_pred), 70)),
            metrics={"mse": mse, "directional_accuracy": dir_acc, "directional_baseline": baseline},
            ensemble_weights=weights, available_models=list(models.keys()),
            feature_importances=self._merge_feature_importances(models, weights, transform_meta["feature_names"]),
            scaler_center=scaler.center_.tolist(), scaler_scale=scaler.scale_.tolist(),
            input_feature_names=features,
            pca_groups=transform_meta["pca_groups"],
            pca_components=transform_meta["pca_components"],
            pca_means=transform_meta["pca_means"],
            pca_explained_variance=transform_meta["pca_explained_variance"],
            _runtime_models=models
        )

    def predict_latest(self, feat_df: pd.DataFrame, artifact: LinearModelArtifact) -> Dict[str, Any]:
        """가장 최근 시점의 데이터를 바탕으로 모델의 예측 신호를 생성합니다."""
        latest = feat_df.iloc[-1]
        latest_df = pd.DataFrame([latest])
        x = self.transform_with_artifact(latest_df, artifact)

        if artifact.model_type == "ensemble":
            if not artifact._runtime_models: raise RuntimeError("모델이 로드되지 않았습니다.")
            pred = float(self.predict_with_artifact(latest_df, artifact)[0])
            importances = artifact.feature_importances or {}
            top_features = [{"feature": f, "coefficient": float(v), "abs_weight": float(v)} for f, v in sorted(importances.items(), key=lambda x: x[1], reverse=True)[:5]]
        else:
            coeffs = np.array(artifact.coefficients)
            pred = float(x.reshape(-1) @ coeffs + artifact.intercept)
            top_features = [{"feature": f, "coefficient": float(c), "abs_weight": abs(c)} for f, c in sorted(zip(artifact.feature_names, coeffs), key=lambda x: abs(x[1]), reverse=True)[:5]]

        signal = "BULLISH" if pred > artifact.threshold else "BEARISH" if pred < -artifact.threshold else "NEUTRAL"
        
        return {
            "timestamp": latest["ts"].isoformat(),
            "pred_return_next_horizon": float(pred),
            "signal": signal,
            "threshold": artifact.threshold,
            "top_features": top_features,
            "model_type": artifact.model_type,
        }


def save_model(path: str, artifact: LinearModelArtifact) -> None:
    """아티팩트 메타데이터와 개별 앙상블 모델 파일을 함께 저장합니다."""
    if artifact.model_type == "ensemble" and artifact._runtime_models:
        model_dir = os.path.dirname(path) or "."
        stem = os.path.splitext(os.path.basename(path))[0]
        saved_files = {}

        for name, model in artifact._runtime_models.items():
            ext = {"lightgbm": ".txt", "xgboost": ".json", "catboost": ".cbm"}.get(name, ".bin")
            file_name = f"{stem}_{name}{ext}"
            full_path = os.path.join(model_dir, file_name)
            if hasattr(model, "booster_"): model.booster_.save_model(full_path)
            else: model.save_model(full_path)
            saved_files[name] = file_name
        
        artifact.model_files = saved_files
        artifact.available_models = list(saved_files.keys())

    with open(path, "w", encoding="utf-8") as f:
        json.dump(artifact.to_dict(), f, ensure_ascii=False, indent=2)


def load_model(path: str) -> LinearModelArtifact:
    """JSON 메타데이터를 로드하고 개별 모델 파일들을 복원합니다."""
    with open(path, "r", encoding="utf-8") as f:
        artifact = LinearModelArtifact.from_dict(json.load(f))

    if artifact.model_type == "ensemble" and artifact.model_files:
        model_dir = os.path.dirname(path) or "."
        runtime_models = {}
        for name, rel_path in artifact.model_files.items():
            full_path = os.path.join(model_dir, rel_path)
            if not os.path.exists(full_path): continue
            
            try:
                if name == "lightgbm": 
                    runtime_models[name] = LGBBooster(model_file=full_path)
                elif name == "xgboost":
                    m = XGBRegressor(); m.load_model(full_path); runtime_models[name] = m
                elif name == "catboost":
                    m = CatBoostRegressor(); m.load_model(full_path); runtime_models[name] = m
            except Exception as e:
                logger.warning(f"모델 로드 실패: {name} | {e}")
        
        artifact._runtime_models = runtime_models
    return artifact
