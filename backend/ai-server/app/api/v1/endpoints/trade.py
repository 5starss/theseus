from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from app.trading.orchestrator import orchestrate_trading, run_news_agent
from app.trading.auto_trade import (
    AutoTradeConfigRequest,
    auto_trade_service,
)
from app.trading.agent_response_store import list_agent_response_statuses
from app.shared.rag.ingest_pipeline import RAGIngestPipeline

router = APIRouter()

TICKER_PATTERN = r"^\d{6}$"
news_ingest_pipeline = RAGIngestPipeline()


@router.get("/news", response_model=Dict[str, Any])
async def run_news_agent_endpoint(
    ticker: str = Query(..., pattern=TICKER_PATTERN, description="종목 코드"),
    question: str = Query("이 종목의 향후 단기 주가 방향은 어떨까?", description="뉴스 분석 질문"),
) -> Dict[str, Any]:
    """
    뉴스 에이전트만 단독 호출하여 특정 종목에 대한 뉴스/커뮤니티 기반 분석 카드를 반환합니다.
    """
    try:
        news_card = run_news_agent(ticker=ticker, question=question)
        return {"status": "ok", "news_card": news_card}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/news/ingest", response_model=Dict[str, Any])
async def ingest_news_endpoint(
    ticker: str = Query(..., pattern=TICKER_PATTERN, description="종목 코드"),
    community_limit: int = Query(15, ge=0, le=100, description="수집할 커뮤니티 글 수"),
    reset_collection: bool = Query(False, description="기존 뉴스 컬렉션 초기화 여부"),
    background_tasks: BackgroundTasks = None,
) -> Dict[str, Any]:
    """
    특정 종목의 뉴스/커뮤니티 문서를 수집하고 ChromaDB에 색인합니다.
    """
    try:
        if background_tasks:
            background_tasks.add_task(
                news_ingest_pipeline.run,
                ticker=ticker,
                community_limit=community_limit,
                reset_collection=reset_collection,
            )
            return {
                "status": "ok",
                "message": "백그라운드에서 뉴스 색인을 시작합니다.",
                "ticker": ticker,
                "community_limit": community_limit,
                "reset_collection": reset_collection,
                "timestamp": datetime.now().isoformat(),
            }

        result = news_ingest_pipeline.run(
            ticker=ticker,
            community_limit=community_limit,
            reset_collection=reset_collection,
        )
        return {
            "status": "ok",
            "message": "뉴스 색인 완료",
            "result": result.to_dict(),
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


@router.get("/auto/agent-status", response_model=Dict[str, Any])
async def get_agent_response_status(
    user_id: Optional[int] = Query(None, description="조회할 사용자 ID"),
    trade_date: Optional[str] = Query(None, description="조회 기준일 (YYYY-MM-DD)"),
) -> Dict[str, Any]:
    return {
        "status": "ok",
        "items": list_agent_response_statuses(user_id=user_id, trade_date=trade_date),
    }
