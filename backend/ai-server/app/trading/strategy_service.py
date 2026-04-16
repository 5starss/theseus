import logging
from datetime import datetime
from typing import Dict, Optional

from app.trading.constants import KST

logger = logging.getLogger(__name__)


def resolve_strategy_slot(strategy_slot: Optional[str] = None) -> str:
    """오전/오후 슬롯을 결정합니다. 명시되지 않은 경우 현재 KST 시간을 기준으로 삼습니다."""
    if strategy_slot in {"morning", "afternoon"}:
        return str(strategy_slot)
    return "morning" if datetime.now(KST).hour < 12 else "afternoon"


def build_signal_weights(strategy_slot: str) -> Dict[str, int]:
    """시간대에 따라 뉴스와 퀀트 비중을 다르게 설정합니다."""
    if strategy_slot == "afternoon":
        return {"news_weight": 40, "quant_weight": 60}
    return {"news_weight": 60, "quant_weight": 40}


def build_strategy_profile(invest_style: str, user_investment_style: str = "GROWTH") -> Dict[str, str]:
    """
    사용자의 스타일(성장/안정 등)과 서비스 스타일(Long/Short)을 결합하여 
    투자 성향 요약과 에이전트용 특수 프롬프트를 생성합니다.
    """
    direction = str(invest_style or "LONG").upper()
    risk_pref = str(user_investment_style or "GROWTH").upper()

    risk_map = {
        "BALANCED": "conservative",
        "GROWTH": "moderate",
        "AGGRESSIVE": "aggressive",
    }
    risk_type = risk_map.get(risk_pref, "moderate")

    if direction == "SHORT":
        return {
            "invest_style": "SHORT",
            "user_investment_style": risk_pref,
            "news_question": "이 종목의 당일~향후 1~3거래일 단기 주가 방향과 모멘텀은 어떨까?",
            "risk_type": risk_type,
            "strategy_prompt": (
                f"사용자 투자 성향은 {risk_pref}이며, AI에게 원하는 투자 방향은 단타입니다. "
                "단기 모멘텀과 변동성을 우선 고려하되 사용자 리스크 성향에 맞는 공격성으로 판단하세요."
            ),
        }
    
    return {
        "invest_style": "LONG",
        "user_investment_style": risk_pref,
        "news_question": "이 종목의 향후 수주~수개월 관점에서 중기 추세와 투자 매력은 어떨까?",
        "risk_type": risk_type,
        "strategy_prompt": (
            f"사용자 투자 성향은 {risk_pref}이며, AI에게 원하는 투자 방향은 장기 투자입니다. "
            "원금 손실 허용 범위는 사용자 성향에 맞추고 중기 추세와 지속 가능성을 우선 고려하세요."
        ),
    }
