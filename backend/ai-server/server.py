import os
import logging
from typing import Any, Dict, Optional
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks

from app.trading.scheduler import BatchScheduler
from app.trading.orchestrator import orchestrate_trading
from app.trading.batch_feature_generator import run_daily_batch_preparation
from app.trading.auto_trade import (
    AutoTradeConfigRequest,
    auto_trade_service,
)

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Server - Trade Edition")
scheduler = BatchScheduler()

@app.on_event("startup")
def startup_event():
    logger.info("서버 시작: 정기 배치 스케줄러 가동")
    scheduler.start()

@app.on_event("shutdown")
def shutdown_event():
    logger.info("서버 종료: 배치 스케줄러 중지")
    scheduler.shutdown()

TICKER_PATTERN = r"^\d{6}$"

@app.get("/health")
def health_check() -> Dict[str, str]:
    return {"status": "healthy", "message": "AI Auto-Trading Server is running"}


@app.post("/v1/quant/batch-prepare-all")
def trigger_batch_prepare_all(
    days: int = Query(730, description="수집된 데이터의 캔들 기간 (730=2년, 0=오늘)"),
    background_tasks: BackgroundTasks = None
) -> Dict[str, Any]:
    """
    모든 종목에 대해 RAG 데이터 증분 수집 및 Quant 피처 생성을 수행하는 통합 배치 작업 (수동 트리거)
    """
    if background_tasks:
        background_tasks.add_task(run_daily_batch_preparation, days=days)
        msg = f"백그라운드에서 통합 배치 작업을 시작합니다. (days={days})"
    else:
        run_daily_batch_preparation(days=days)
        msg = f"통합 배치 작업 완료. (days={days})"
        
    return {
        "status": "ok",
        "message": msg,
        "timestamp": datetime.now().isoformat()
    }


@app.get("/v1/trade/orchestrate")
def orchestrate_trade_endpoint(
    ticker: str = Query(..., pattern=TICKER_PATTERN, description="종목 코드"),
    available_cash: int = Query(5000000, description="현재 가용 예수금"),
    user_id: Optional[int] = Query(None, description="자동매매 대상 사용자 ID"),
    account_type: str = Query("USER", description="주문에 사용할 계좌 타입(USER 또는 AI)")
) -> Dict[str, Any]:
    """
    오케스트레이터를 수동 호출하여 특정 종목에 대한 AI 매매 판정(Order Card)을 반환합니다.
    (내부적으로 News / Quant / Judge 에이전트를 순차 호출)
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
        logger.error(f"[{ticker}] 오케스트레이터 수행 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/trade/auto/config")
def get_auto_trade_config(
    user_id: int = Query(..., description="자동매매 대상 사용자 ID"),
) -> Dict[str, Any]:
    return {"status": "ok", "config": auto_trade_service.get_config(user_id).model_dump()}


@app.get("/v1/trade/auto/configs")
def list_auto_trade_configs() -> Dict[str, Any]:
    return {
        "status": "ok",
        "configs": [config.model_dump() for config in auto_trade_service.list_configs()],
    }


@app.post("/v1/trade/auto/config")
def upsert_auto_trade_config(
    request: AutoTradeConfigRequest,
    user_id: int = Query(..., description="자동매매 대상 사용자 ID"),
) -> Dict[str, Any]:
    return auto_trade_service.enable_and_prepare(user_id, request)


@app.post("/v1/trade/auto/run")
def run_auto_trade_now(
    user_id: int = Query(..., description="자동매매 대상 사용자 ID"),
    force: bool = Query(True, description="시장 시간 외에도 강제 실행할지 여부"),
) -> Dict[str, Any]:
    return auto_trade_service.run_user_cycle(user_id, force=force)
