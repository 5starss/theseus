from datetime import datetime
from typing import Any, Dict
from fastapi import APIRouter, Query, BackgroundTasks
from app.trading.scheduler_instance import scheduler

router = APIRouter()


@router.post("/batch-prepare-all", response_model=Dict[str, Any])
async def trigger_batch_prepare_all(
    days: int = Query(730, description="수집된 데이터의 캔들 기간 (730=2년, 0=오늘)"),
    background_tasks: BackgroundTasks = None
) -> Dict[str, Any]:
    """
    모든 종목에 대해 RAG 데이터 증분 수집 및 Quant 피처 생성을 수행하는 통합 배치 작업 (수동 트리거)
    """
    if background_tasks:
        background_tasks.add_task(scheduler.run_batch_prepare, days=days)
        msg = f"백그라운드에서 통합 배치 작업을 시작합니다. (days={days})"
    else:
        scheduler.run_batch_prepare(days=days)
        msg = f"통합 배치 작업 완료. (days={days})"
        
    return {
        "status": "ok",
        "message": msg,
        "timestamp": datetime.now().isoformat()
    }
