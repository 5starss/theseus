import logging
from datetime import datetime
from typing import Dict, Any

from app.quant.sources import get_all_tickers_from_db
from app.quant.preparation import prepare_feature_df
from app.shared.rag.ingest_pipeline import RAGIngestPipeline

logger = logging.getLogger(__name__)

def run_daily_batch_preparation(
    data_dir: str, 
    horizon_minutes: int = 5, 
    feature_profile: str = "mtf",
    days: int = 730
) -> Dict[str, Any]:
    """
    DB의 모든 종목 코드를 조회하여:
    1) RAG 뉴스 수집 및 벡터 DB 색인
    2) 퀀트 피처 생성 및 S3 업로드
    를 수행합니다.

    """
    try:
        tickers = get_all_tickers_from_db()
    except Exception as e:
        logger.error("DB 종목 로드 실패: %s", e)
        return {"status": "error", "message": f"DB load failed: {e}"}
        
    if not tickers:
        logger.warning("배치 처리할 종목이 DB에 없습니다.")
        return {"status": "ok", "message": "No tickers found", "success_count": 0}
        
    logger.info("일일 통합 배치(RAG + Quant) 시작: %d 종목", len(tickers))
    
    success_count = 0
    failures = []
    
    rag_pipeline = RAGIngestPipeline()
    
    for idx, ticker in enumerate(tickers):
        logger.info("[%d/%d] %s 통합 배치 처리 중...", idx + 1, len(tickers), ticker)
        try:
            # 1) News RAG Ingest (기존 컬렉션 유지하며 추가 데이터 색인)
            logger.info("  -> [News RAG] 수집 및 색인 중...")
            rag_pipeline.run(ticker=ticker, reset_collection=(idx == 0)) # 첫 종목일 때만 초기화
            
            # 2) Quant Feature Generation
            logger.info("  -> [Quant] 피처 생성 및 S3 업로드 중...")
            raw_path, feat_path, feat_df = prepare_feature_df(
                ticker=ticker,
                data_dir=data_dir,
                run_fetch=True,
                run_feature_extract=True,
                horizon_minutes=horizon_minutes,
                feature_profile=feature_profile,
                recent_window_days=None,
                days=days,
            )
            success_count += 1
            logger.info("  -> %s 처리 성공", ticker)
        except Exception as e:
            logger.error("  -> %s 처리 실패: %s", ticker, str(e))
            failures.append({"ticker": ticker, "error": str(e)})
            
    result = {
        "status": "ok",
        "total_tickers": len(tickers),
        "success_count": success_count,
        "failure_count": len(failures),
        "failures": failures,
        "completed_at": datetime.now().isoformat()
    }
    logger.info("일일 배치 피처 생성 완료: %d 성공, %d 실패", success_count, len(failures))
    return result
