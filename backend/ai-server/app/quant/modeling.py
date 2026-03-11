import json
import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import RobustScaler

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

    def __init__(self, model_type: str = "ensemble"):
        self.model_type = model_type

    def _prepare_xy(self, df: pd.DataFrame, feature_cols: List[str]) -> Tuple[np.ndarray, np.ndarray]:
        """피처와 타겟 변수를 Numpy 배열로 변환합니다."""
        x = df[feature_cols].astype(float).to_numpy()
        y = df["target_return"].astype(float).to_numpy()
        return x, y

    def train(self, feat_df: pd.DataFrame, feature_cols: Optional[List[str]] = None) -> LinearModelArtifact:
        """지정된 모드(linear/ensemble)에 따라 모델을 학습합니다."""
        feature_cols = feature_cols or [c for c in self.DEFAULT_FEATURES if c in feat_df.columns]
        
        # Train/Test Time-series split (보수적인 8:2 분할)
        split_idx = int(len(feat_df) * 0.8)
        train_df = feat_df.iloc[:split_idx]
        test_df = feat_df.iloc[split_idx:]
        
        x_tr, y_tr = self._prepare_xy(train_df, feature_cols)
        x_te, y_te = self._prepare_xy(test_df, feature_cols)
        
        scaler = RobustScaler()
        scaler.fit(x_tr)
        x_tr_scaled = scaler.transform(x_tr)
        x_te_scaled = scaler.transform(x_te)

        if self.model_type == "linear":
            return self._train_linear(x_tr_scaled, y_tr, x_te_scaled, y_te, feature_cols, scaler)
        return self._train_ensemble(x_tr_scaled, y_tr, x_te_scaled, y_te, feature_cols, scaler)

    def _train_linear(self, x_tr, y_tr, x_te, y_te, features, scaler) -> LinearModelArtifact:
        """선형 회귀 알고리즘을 사용하여 모델을 학습합니다."""
        x_tr_aug = np.hstack([x_tr, np.ones((x_tr.shape[0], 1))])
        coeffs_aug, *_ = np.linalg.lstsq(x_tr_aug, y_tr, rcond=None)
        coeffs, intercept = coeffs_aug[:-1], float(coeffs_aug[-1])
        
        pred = x_te @ coeffs + intercept
        mse = float(np.mean((pred - y_te) ** 2))
        dir_acc = float(np.mean(np.sign(pred) == np.sign(y_te)))
        
        return LinearModelArtifact(
            feature_names=features, coefficients=coeffs.tolist(), intercept=intercept,
            threshold=float(np.std(y_tr)*0.25),
            metrics={"mse": mse, "directional_accuracy": dir_acc},
            scaler_center=scaler.center_.tolist(), scaler_scale=scaler.scale_.tolist()
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

    def _train_ensemble(self, x_tr, y_tr, x_te, y_te, features, scaler) -> LinearModelArtifact:
        """LightGBM, XGBoost, CatBoost의 성능 가중치 기반 앙상블 모델을 학습합니다."""
        models, test_preds, tr_preds = {}, {}, {}
        
        if LGBMRegressor:
            m = LGBMRegressor(n_estimators=300, learning_rate=0.03, verbose=-1, random_state=42)
            m.fit(x_tr, y_tr)
            models["lightgbm"] = m
            test_preds["lightgbm"] = self._predict_safe(m, x_te, features)
            tr_preds["lightgbm"] = self._predict_safe(m, x_tr, features)
        
        if XGBRegressor:
            m = XGBRegressor(n_estimators=350, learning_rate=0.03, verbosity=0, random_state=42)
            m.fit(x_tr, y_tr)
            models["xgboost"] = m
            test_preds["xgboost"] = self._predict_safe(m, x_te, features)
            tr_preds["xgboost"] = self._predict_safe(m, x_tr, features)

        if CatBoostRegressor:
            m = CatBoostRegressor(iterations=400, learning_rate=0.03, verbose=False, random_seed=42)
            m.fit(x_tr, y_tr)
            models["catboost"] = m
            test_preds["catboost"] = self._predict_safe(m, x_te, features)
            tr_preds["catboost"] = self._predict_safe(m, x_tr, features)

        if not models: return self._train_linear(x_tr, y_tr, x_te, y_te, features, scaler)

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
            model_type="ensemble", feature_names=features, coefficients=[], intercept=0.0,
            threshold=float(np.percentile(np.abs(ens_pred), 70)),
            metrics={"mse": mse, "directional_accuracy": dir_acc, "directional_baseline": baseline},
            ensemble_weights=weights, available_models=list(models.keys()),
            feature_importances=self._merge_feature_importances(models, weights, features),
            scaler_center=scaler.center_.tolist(), scaler_scale=scaler.scale_.tolist(),
            _runtime_models=models
        )

    def predict_latest(self, feat_df: pd.DataFrame, artifact: LinearModelArtifact) -> Dict[str, Any]:
        """가장 최근 시점의 데이터를 바탕으로 모델의 예측 신호를 생성합니다."""
        latest = feat_df.iloc[-1]
        x = latest[artifact.feature_names].astype(float).to_numpy().reshape(1, -1)
        
        # Scaling
        if artifact.scaler_center and artifact.scaler_scale:
            center, scale = np.array(artifact.scaler_center), np.array(artifact.scaler_scale)
            x = (x - center) / np.where(np.abs(scale) > 1e-12, scale, 1.0)

        if artifact.model_type == "ensemble":
            if not artifact._runtime_models: raise RuntimeError("모델이 로드되지 않았습니다.")
            pred = sum((artifact.ensemble_weights.get(k, 0) * self._predict_safe(m, x, artifact.feature_names)[0]) for k, m in artifact._runtime_models.items())
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
