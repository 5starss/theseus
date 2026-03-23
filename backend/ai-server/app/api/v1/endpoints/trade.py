from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query
from app.trading.orchestrator import orchestrate_trading
from app.trading.auto_trade import (
    AutoTradeConfigRequest,
    auto_trade_service,
)

router = APIRouter()

TICKER_PATTERN = r"^\d{6}$"


@router.get("/orchestrate", response_model=Dict[str, Any])
async def orchestrate_trade_endpoint(
    ticker: str = Query(..., pattern=TICKER_PATTERN, description="종목 코드"),
    available_cash: int = Query(5000000, description="현재 가용 예수금"),
    user_id: Optional[int] = Query(None, description="자동매매 대상 사용자 ID"),
    account_type: str = Query("USER", description="주문에 사용할 계좌 타입(USER 또는 AI)")
) -> Dict[str, Any]:
    """
    오케스트레이터를 수동 호출하여 특정 종목에 대한 AI 매매 판정(Order Card)을 반환합니다.
    """
    try:
        order_card = orchestrate_trading(
            ticker=ticker,
            available_cash=available_cash,
            user_id=user_id,
            account_type=account_type,
        )
        return {"status": "ok", "order_card": order_card}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auto/config", response_model=Dict[str, Any])
async def get_auto_trade_config(
    user_id: int = Query(..., description="자동매매 대상 사용자 ID"),
) -> Dict[str, Any]:
    return {"status": "ok", "config": auto_trade_service.get_config(user_id).model_dump()}


@router.get("/auto/configs", response_model=Dict[str, Any])
async def list_auto_trade_configs() -> Dict[str, Any]:
    return {
        "status": "ok",
        "configs": [config.model_dump() for config in auto_trade_service.list_configs()],
    }


@router.post("/auto/config", response_model=Dict[str, Any])
async def upsert_auto_trade_config(
    request: AutoTradeConfigRequest,
    user_id: int = Query(..., description="자동매매 대상 사용자 ID"),
) -> Dict[str, Any]:
    return auto_trade_service.enable_and_prepare(user_id, request)


@router.post("/auto/run", response_model=Dict[str, Any])
async def run_auto_trade_now(
    user_id: int = Query(..., description="자동매매 대상 사용자 ID"),
    force: bool = Query(True, description="시장 시간 외에도 강제 실행할지 여부"),
) -> Dict[str, Any]:
    return auto_trade_service.run_user_cycle(user_id, force=force)
