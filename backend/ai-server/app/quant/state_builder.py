"""
Quant State Builder
===================
raw feature row -> 해석된 상태(State) 중심 스키마로 변환하는 단일 책임 모듈.

설계 문서: QUANT_STATE_SCHEMA_DESIGN.md

출력 블록:
  1. market_state       - 장중 시장 사실 묘사
  2. multi_timeframe    - 타임프레임 방향 정렬
  3. symbol_profile     - 종목 구조적 성격 (배치 기반)
  4. risk_context       - 진입 판단 메타 평가
  5. supporting_metrics - LLM 근거용 최소 raw 수치
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))

# ──────────────────────────────────────────────
# 1. 임계치 상수 테이블
# ──────────────────────────────────────────────

# --- momentum_strength ---
MOMENTUM_STRONG_THRESHOLD = 0.01
MOMENTUM_MODERATE_THRESHOLD = 1e-9  # strictly > 0

# --- overheat_state (RSI 기반) ---
RSI_OVERHEAT_HIGH = 75
RSI_OVERHEAT_MODERATE = 65

# --- volume_state (Z-Score 기반) ---
VOLUME_HIGH_Z = 1.5
VOLUME_MODERATE_Z = 0.5

# --- price_vs_vwap ---
VWAP_ABOVE_THRESHOLD = 0.005
VWAP_BELOW_THRESHOLD = -0.005

# --- intraday_position (close_high_ratio) ---
POSITION_NEAR_HIGH = 0.8
POSITION_NEAR_LOW = 0.2

# --- volatility_state (vol_20 기반) ---
VOLATILITY_HIGH_THRESHOLD = 0.015
VOLATILITY_LOW_THRESHOLD = 0.005

# --- session_phase (session_progress 기반, 0~1) ---
SESSION_OPEN_END = 0.15       # 시초 구간
SESSION_MIDDAY_END = 0.65     # 중반 구간
SESSION_CLOSING_START = 0.85  # 마감 구간

# --- intraday_trend (mom_15 기반) ---
TREND_UP_THRESHOLD = 0.003
TREND_DOWN_THRESHOLD = -0.003

# --- multi_timeframe 방향 판단 (각 타임프레임 trend 값) ---
MTF_UP_THRESHOLD = 0.002
MTF_DOWN_THRESHOLD = -0.002

# --- multi_timeframe alignment_score 가중치 ---
MTF_WEIGHTS = {
    "m1": 0.10,
    "m5": 0.20,
    "m15": 0.25,
    "h1": 0.20,
    "d1": 0.25,
}

# --- symbol_profile: trend_efficiency (rolling_sharpe 대리지표) ---
# feature_engineer 에서 rolling_sharpe 를 직접 계산하지 않으므로
# mtf_1d_trend 절대값 대비 mtf_1d_vol_20 비율로 대리 계산
TREND_EFFICIENCY_HIGH = 1.0
TREND_EFFICIENCY_MEDIUM = 0.3

# --- symbol_profile: drawdown_risk (rv_30 기반) ---
DRAWDOWN_RISK_LOW = 0.03
DRAWDOWN_RISK_MEDIUM = 0.07

# --- risk_context: entry_risk 점수 기반 ---
ENTRY_RISK_HIGH_THRESHOLD = 3
ENTRY_RISK_LOW_THRESHOLD = 1

# --- risk_context: reward_risk_quality ---
RRQ_ALIGNMENT_GOOD = 0.7
RRQ_ALIGNMENT_POOR = 0.4

# --- risk_context: signal_confidence ---
CONFIDENCE_ALIGNMENT_HIGH = 0.7

# ──────────────────────────────────────────────
# 2. 헬퍼 함수
# ──────────────────────────────────────────────

def _safe_float(value: Any, default: float = 0.0) -> float:
    """안전하게 float 변환."""
    if value is None:
        return default
    try:
        import math
        v = float(value)
        return default if math.isnan(v) or math.isinf(v) else v
    except (TypeError, ValueError):
        return default


def _classify(value: float, thresholds: list[tuple[float, str]], default: str) -> str:
    """value 를 내림차순 임계치 목록과 비교해 레이블을 반환."""
    for threshold, label in thresholds:
        if value >= threshold:
            return label
    return default


def _direction(trend_value: float) -> str:
    """추세 값을 up/neutral/down 으로 변환."""
    if trend_value >= MTF_UP_THRESHOLD:
        return "up"
    if trend_value <= MTF_DOWN_THRESHOLD:
        return "down"
    return "neutral"


def _direction_score(direction: str) -> float:
    """방향을 수치로 변환 (alignment_score 계산용)."""
    return {"up": 1.0, "neutral": 0.5, "down": 0.0}.get(direction, 0.5)


# ──────────────────────────────────────────────
# 3. 블록별 빌더
# ──────────────────────────────────────────────

def _build_market_state(row: Dict[str, Any]) -> Dict[str, str]:
    """장중 실시간 데이터를 해석한 사실 묘사 블록."""
    mom_5 = _safe_float(row.get("mom_5"))
    rsi_14 = _safe_float(row.get("rsi_14"), 50.0)
    volume_z20 = _safe_float(row.get("volume_z20"))
    dist_vwap = _safe_float(row.get("dist_vwap"))
    close_high_ratio = _safe_float(row.get("close_high_ratio"), 0.5)
    session_progress = _safe_float(row.get("session_progress"), 0.5)
    vol_20 = _safe_float(row.get("vol_20"))
    mom_15 = _safe_float(row.get("mom_15"))

    # intraday_trend
    intraday_trend = _classify(
        mom_15,
        [(TREND_UP_THRESHOLD, "up")],
        "neutral"
    )
    if mom_15 <= TREND_DOWN_THRESHOLD:
        intraday_trend = "down"

    # momentum_strength
    momentum_strength = _classify(
        mom_5,
        [(MOMENTUM_STRONG_THRESHOLD, "strong"), (MOMENTUM_MODERATE_THRESHOLD, "moderate")],
        "weak",
    )

    # volatility_state
    volatility_state = _classify(
        vol_20,
        [(VOLATILITY_HIGH_THRESHOLD, "expanding"), (VOLATILITY_LOW_THRESHOLD, "normal")],
        "contracting",
    )

    # volume_state
    volume_state = _classify(
        volume_z20,
        [(VOLUME_HIGH_Z, "high"), (VOLUME_MODERATE_Z, "moderate")],
        "normal",
    )

    # price_vs_vwap
    if dist_vwap > VWAP_ABOVE_THRESHOLD:
        price_vs_vwap = "above"
    elif dist_vwap < VWAP_BELOW_THRESHOLD:
        price_vs_vwap = "below"
    else:
        price_vs_vwap = "near"

    # overheat_state
    overheat_state = _classify(
        rsi_14,
        [(RSI_OVERHEAT_HIGH, "high"), (RSI_OVERHEAT_MODERATE, "moderate")],
        "low",
    )

    # intraday_position
    intraday_position = _classify(
        close_high_ratio,
        [(POSITION_NEAR_HIGH, "near_high")],
        "mid",
    )
    if close_high_ratio <= POSITION_NEAR_LOW:
        intraday_position = "near_low"

    # session_phase
    if session_progress <= SESSION_OPEN_END:
        session_phase = "opening"
    elif session_progress <= SESSION_MIDDAY_END:
        session_phase = "midday"
    elif session_progress >= SESSION_CLOSING_START:
        session_phase = "closing"
    else:
        session_phase = "late_midday"

    return {
        "intraday_trend": intraday_trend,
        "momentum_strength": momentum_strength,
        "volatility_state": volatility_state,
        "volume_state": volume_state,
        "price_vs_vwap": price_vs_vwap,
        "overheat_state": overheat_state,
        "intraday_position": intraday_position,
        "session_phase": session_phase,
    }


def _build_multi_timeframe(row: Dict[str, Any]) -> Dict[str, Any]:
    """타임프레임별 방향 및 alignment_score 를 계산."""
    # 각 타임프레임 trend 값 추출 (feature_engineer 의 mtf_* 컬럼 사용)
    m1_trend = _safe_float(row.get("mom_5"))           # 1분봉 대리 = 5분 모멘텀
    m5_trend = _safe_float(row.get("mtf_5m_trend"))
    m15_trend = _safe_float(row.get("mtf_15m_trend"))
    h1_trend = _safe_float(row.get("mtf_60m_trend"))
    d1_trend = _safe_float(row.get("mtf_1d_trend"))

    directions = {
        "m1": _direction(m1_trend),
        "m5": _direction(m5_trend),
        "m15": _direction(m15_trend),
        "h1": _direction(h1_trend),
        "d1": _direction(d1_trend),
    }

    # alignment_score 계산 (가중 평균)
    alignment_score = sum(
        _direction_score(directions[tf]) * weight
        for tf, weight in MTF_WEIGHTS.items()
    )
    alignment_score = round(alignment_score, 2)

    return {
        **directions,
        "alignment_score": alignment_score,
    }


def _build_symbol_profile(row: Dict[str, Any]) -> Dict[str, str]:
    """종목의 구조적 성격 블록. 느리게 변하는 값 기반."""
    # trend_efficiency: d1 trend / d1 vol = 샤프 대리지표
    d1_trend = abs(_safe_float(row.get("mtf_1d_trend")))
    d1_vol = _safe_float(row.get("mtf_1d_vol_20"), 0.01)
    if d1_vol <= 0:
        d1_vol = 0.01
    sharpe_proxy = d1_trend / d1_vol

    trend_efficiency = _classify(
        sharpe_proxy,
        [(TREND_EFFICIENCY_HIGH, "high"), (TREND_EFFICIENCY_MEDIUM, "medium")],
        "low",
    )

    # drawdown_risk: rv_30 (실현변동성) 기반
    rv_30 = _safe_float(row.get("rv_30"))
    drawdown_risk = _classify(
        rv_30,
        [(DRAWDOWN_RISK_MEDIUM, "high"), (DRAWDOWN_RISK_LOW, "medium")],
        "low",
    )

    # volatility_character: vol_20 기반 안정성
    vol_20 = _safe_float(row.get("vol_20"))
    if vol_20 < VOLATILITY_LOW_THRESHOLD:
        volatility_character = "stable"
    elif vol_20 < VOLATILITY_HIGH_THRESHOLD:
        volatility_character = "moderate"
    else:
        volatility_character = "volatile"

    # mean_reversion_tendency: skew_30 기반
    skew_30 = _safe_float(row.get("skew_30"))
    if abs(skew_30) < 0.3:
        mean_reversion = "low"
    elif abs(skew_30) < 0.8:
        mean_reversion = "medium"
    else:
        mean_reversion = "high"

    return {
        "group": "unknown",  # 배치에서 별도 분류 갱신
        "trend_efficiency": trend_efficiency,
        "drawdown_risk": drawdown_risk,
        "volatility_character": volatility_character,
        "mean_reversion_tendency": mean_reversion,
    }


def _build_risk_context(
    market_state: Dict[str, str],
    symbol_profile: Dict[str, str],
    multi_timeframe: Dict[str, Any],
) -> Dict[str, str]:
    """진입 리스크 + 손익비 품질 + 신호 신뢰도 메타 평가."""

    # --- entry_risk ---
    risk_score = 0
    if market_state["overheat_state"] == "high":
        risk_score += 1
    if market_state["intraday_position"] == "near_high":
        risk_score += 1
    if market_state["price_vs_vwap"] == "above":
        risk_score += 1
    if market_state["volatility_state"] == "expanding":
        risk_score += 1

    if risk_score >= ENTRY_RISK_HIGH_THRESHOLD:
        entry_risk = "high"
    elif risk_score <= ENTRY_RISK_LOW_THRESHOLD:
        entry_risk = "low"
    else:
        entry_risk = "medium"

    # --- reward_risk_quality ---
    alignment = multi_timeframe.get("alignment_score", 0.5)
    te = symbol_profile["trend_efficiency"]
    dr = symbol_profile["drawdown_risk"]

    if te == "high" and dr == "low" and alignment >= RRQ_ALIGNMENT_GOOD:
        reward_risk_quality = "good"
    elif te == "low" and dr == "high" and alignment < RRQ_ALIGNMENT_POOR:
        reward_risk_quality = "poor"
    else:
        reward_risk_quality = "fair"

    # --- signal_confidence ---
    confidence_score = 0
    if alignment >= CONFIDENCE_ALIGNMENT_HIGH:
        confidence_score += 1
    if market_state["volume_state"] == "high":
        confidence_score += 1
    if entry_risk != "high":
        confidence_score += 1
    if market_state["intraday_trend"] in ("up", "down"):  # 방향성 명확
        confidence_score += 1

    if confidence_score >= 3:
        signal_confidence = "high"
    elif confidence_score >= 2:
        signal_confidence = "medium"
    else:
        signal_confidence = "low"

    return {
        "entry_risk": entry_risk,
        "reward_risk_quality": reward_risk_quality,
        "signal_confidence": signal_confidence,
    }


def _build_supporting_metrics(row: Dict[str, Any]) -> Dict[str, Any]:
    """LLM 근거용 최소 raw 수치 (5개 고정)."""
    return {
        "mom_5": round(_safe_float(row.get("mom_5")), 4),
        "rsi_14": round(_safe_float(row.get("rsi_14"), 50.0), 1),
        "dist_vwap": round(_safe_float(row.get("dist_vwap")), 4),
        "volume_z20": round(_safe_float(row.get("volume_z20")), 2),
        "mtf_15m_trend": round(_safe_float(row.get("mtf_15m_trend")), 4),
    }


# ──────────────────────────────────────────────
# 4. 메인 엔트리 포인트
# ──────────────────────────────────────────────

def build_quant_state_payload(
    feature_row: Dict[str, Any],
    symbol: str = "000000",
) -> Dict[str, Any]:
    """
    raw feature row 1건을 받아 5-블록 상태 스키마로 변환.

    Parameters
    ----------
    feature_row : dict
        feature_engineer.py 가 생성한 피처 row (DataFrame.iloc[-1].to_dict())
    symbol : str
        종목 코드

    Returns
    -------
    dict
        {symbol, as_of, market_state, multi_timeframe,
         symbol_profile, risk_context, supporting_metrics}
    """
    market_state = _build_market_state(feature_row)
    multi_timeframe = _build_multi_timeframe(feature_row)
    symbol_profile = _build_symbol_profile(feature_row)
    risk_context = _build_risk_context(market_state, symbol_profile, multi_timeframe)
    supporting_metrics = _build_supporting_metrics(feature_row)
    ts_value = feature_row.get("ts")
    if ts_value is None:
        as_of = datetime.now(KST).isoformat()
    elif hasattr(ts_value, "isoformat"):
        try:
            as_of = ts_value.isoformat()
        except Exception:
            as_of = datetime.now(KST).isoformat()
    else:
        try:
            as_of = datetime.fromisoformat(str(ts_value)).astimezone(KST).isoformat()
        except Exception:
            as_of = datetime.now(KST).isoformat()

    return {
        "symbol": symbol,
        "as_of": as_of,
        "market_state": market_state,
        "multi_timeframe": multi_timeframe,
        "symbol_profile": symbol_profile,
        "risk_context": risk_context,
        "supporting_metrics": supporting_metrics,
    }
