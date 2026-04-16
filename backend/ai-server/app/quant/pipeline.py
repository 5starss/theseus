from typing import Any, Dict

from app.quant.agent import QuantAnalysisAgent
from app.quant.preparation import prepare_feature_df
from app.quant.state_builder import build_quant_state_payload


def generate_quant_signal(ticker: str, data_dir: str, run_fetch: bool = True, horizon_minutes: int = 5) -> Dict[str, Any]:
    """최신 피처를 기반으로 LLM Quant 분석 카드를 생성합니다."""
    try:
        raw_path, _, feat_df = prepare_feature_df(
            ticker=ticker,
            data_dir=data_dir,
            run_fetch=run_fetch,
            run_feature_extract=True,
            horizon_minutes=horizon_minutes,
            feature_profile="mtf",
            recent_window_days=None,
        )
    except Exception as exc:
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
    quant_state = build_quant_state_payload(latest_row, symbol=ticker)

    agent = QuantAnalysisAgent()
    card = agent.generate_analysis_card(ticker=ticker, quant_evidence=quant_state)
    return {
        "status": "ok",
        "analysis_card": card,
        "quant_evidence": quant_state,
        "raw_result": {
            "mode": "quant_state_mvp",
            "raw_path": raw_path,
            "feature_profile": "mtf",
            "feature_rows": int(len(feat_df)),
            "horizon_minutes": horizon_minutes,
            "evidence_keys": list(quant_state.keys()),
        },
    }


def build_state_from_feature_row(
    feature_row: Dict[str, Any],
    ticker: str = "000000",
) -> Dict[str, Any]:
    """raw feature row -> 5-블록 상태 스키마 변환."""
    return build_quant_state_payload(feature_row, symbol=ticker)
