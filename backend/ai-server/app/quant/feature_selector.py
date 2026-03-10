import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FeatureSelectionResult:
    selected_features: List[str]
    score_table: pd.DataFrame
    summary: Dict[str, Any]


class FeatureValiditySelector:
    """시계열 피처의 예측력/안정성/중복도를 기준으로 유효 피처를 선별합니다."""

    EXCLUDE_COLUMNS = {
        "ts",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "target_return",
        "target_up",
    }

    def __init__(
        self,
        min_abs_ic: float = 0.01,
        min_stability: float = 0.20,
        min_coverage: float = 0.99,
        min_unique_ratio: float = 0.001,
        max_pair_corr: float = 0.95,
    ):
        self.min_abs_ic = min_abs_ic
        self.min_stability = min_stability
        self.min_coverage = min_coverage
        self.min_unique_ratio = min_unique_ratio
        self.max_pair_corr = max_pair_corr

    def _candidate_features(self, feat_df: pd.DataFrame) -> List[str]:
        numeric_cols = feat_df.select_dtypes(include=[np.number]).columns.tolist()
        return [c for c in numeric_cols if c not in self.EXCLUDE_COLUMNS]

    @staticmethod
    def _safe_spearman(x: pd.Series, y: pd.Series) -> float:
        v = x.corr(y, method="spearman")
        if pd.isna(v):
            return 0.0
        return float(v)

    @staticmethod
    def _stability(ic_first: float, ic_second: float) -> float:
        denom = abs(ic_first) + abs(ic_second) + 1e-12
        s = 1.0 - abs(ic_first - ic_second) / denom
        return float(max(0.0, min(1.0, s)))

    def _score_feature(self, df: pd.DataFrame, feature: str) -> Dict[str, Any]:
        x = df[feature]
        y = df["target_return"]

        coverage = float(1.0 - x.isna().mean())
        unique_ratio = float(x.nunique(dropna=True) / max(1, len(x)))

        split_idx = len(df) // 2
        ic_all = self._safe_spearman(x, y)
        ic_first = self._safe_spearman(df.iloc[:split_idx][feature], df.iloc[:split_idx]["target_return"])
        ic_second = self._safe_spearman(df.iloc[split_idx:][feature], df.iloc[split_idx:]["target_return"])
        stability = self._stability(ic_first, ic_second)

        abs_ic = abs(ic_all)
        # 안정성이 낮은 피처 점수를 보수적으로 감쇠
        score = abs_ic * (0.5 + 0.5 * stability)

        pass_coverage = coverage >= self.min_coverage
        pass_unique = unique_ratio >= self.min_unique_ratio
        pass_ic = abs_ic >= self.min_abs_ic
        pass_stability = stability >= self.min_stability
        is_valid = pass_coverage and pass_unique and pass_ic and pass_stability

        return {
            "feature": feature,
            "coverage": coverage,
            "unique_ratio": unique_ratio,
            "ic_spearman": ic_all,
            "abs_ic": abs_ic,
            "ic_first_half": ic_first,
            "ic_second_half": ic_second,
            "ic_stability": stability,
            "score": score,
            "pass_coverage": int(pass_coverage),
            "pass_unique": int(pass_unique),
            "pass_ic": int(pass_ic),
            "pass_stability": int(pass_stability),
            "is_valid_pre_corr": int(is_valid),
        }

    def select(self, feat_df: pd.DataFrame, top_k: Optional[int] = None) -> FeatureSelectionResult:
        if feat_df.empty:
            raise ValueError("피처 선택 대상 데이터가 비어 있습니다.")
        if "target_return" not in feat_df.columns:
            raise ValueError("target_return 컬럼이 필요합니다.")

        df = feat_df.sort_values("ts").reset_index(drop=True).copy()
        candidates = self._candidate_features(df)
        if not candidates:
            raise ValueError("선별 가능한 숫자형 피처가 없습니다.")

        rows = [self._score_feature(df, f) for f in candidates]
        score_table = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)

        prelim = score_table[score_table["is_valid_pre_corr"] == 1]["feature"].tolist()
        selected: List[str] = []
        dropped_by_corr = 0

        for feat in prelim:
            keep = True
            for sel in selected:
                corr = abs(float(df[feat].corr(df[sel])))
                if np.isnan(corr):
                    corr = 0.0
                if corr > self.max_pair_corr:
                    keep = False
                    dropped_by_corr += 1
                    break
            if keep:
                selected.append(feat)
            if top_k is not None and len(selected) >= top_k:
                break

        score_table["selected"] = score_table["feature"].isin(selected).astype(int)

        summary = {
            "rows": int(len(df)),
            "candidate_features": int(len(candidates)),
            "valid_before_corr_filter": int(len(prelim)),
            "selected_features": int(len(selected)),
            "dropped_by_corr_filter": int(dropped_by_corr),
            "thresholds": {
                "min_abs_ic": self.min_abs_ic,
                "min_stability": self.min_stability,
                "min_coverage": self.min_coverage,
                "min_unique_ratio": self.min_unique_ratio,
                "max_pair_corr": self.max_pair_corr,
            },
        }
        logger.info(
            "피처 선별 완료 | 후보=%d | 1차통과=%d | 최종=%d",
            len(candidates),
            len(prelim),
            len(selected),
        )
        return FeatureSelectionResult(selected_features=selected, score_table=score_table, summary=summary)
