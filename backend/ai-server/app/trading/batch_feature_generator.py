import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, List

from app.quant.sources import get_all_tickers_from_db
from app.quant.preparation import prepare_feature_df
from app.shared.rag.ingest_pipeline import RAGIngestPipeline

logger = logging.getLogger(__name__)


def _resolve_batch_tickers() -> List[str]:
    try:
        return get_all_tickers_from_db()
    except Exception as e:
        logger.error("DB 종목 로드 실패: %s", e)
        raise


def run_news_rag_batch() -> Dict[str, Any]:
    """
    모든 종목에 대해 뉴스/커뮤니티 RAG 수집 및 색인을 수행합니다.
    """
    try:
        tickers = _resolve_batch_tickers()
    except Exception as e:
        return {"status": "error", "message": f"DB load failed: {e}"}

    if not tickers:
        logger.warning("뉴스 배치 처리할 종목이 DB에 없습니다.")
        return {"status": "ok", "message": "No tickers found", "success_count": 0}

    logger.info("뉴스/RAG 배치 시작: %d 종목", len(tickers))

    success_count = 0
    failures = []
    rag_pipeline = RAGIngestPipeline()

    for idx, ticker in enumerate(tickers):
        logger.info("[%d/%d] %s 뉴스/RAG 처리 중...", idx + 1, len(tickers), ticker)
        try:
            rag_pipeline.run(ticker=ticker, reset_collection=(idx == 0))
            success_count += 1
        except Exception as e:
            logger.error("  -> %s 뉴스/RAG 처리 실패: %s", ticker, str(e))
            failures.append({"ticker": ticker, "error": str(e)})

    status = "ok" if not failures else "partial"
    result = {
        "status": status,
        "batch_type": "news_rag",
        "total_tickers": len(tickers),
        "success_count": success_count,
        "failure_count": len(failures),
        "failures": failures,
        "completed_at": datetime.now().isoformat(),
    }
    logger.info("뉴스/RAG 배치 완료: %d 성공, %d 실패 (status=%s)", success_count, len(failures), status)
    return result


def run_quant_feature_batch(
    data_dir: Optional[str] = None,
    horizon_minutes: int = 5,
    feature_profile: str = "mtf",
    days: int = 730,
) -> Dict[str, Any]:
    """
    모든 종목에 대해 퀀트 피처 생성 및 S3 업로드를 수행합니다.
    """
    if data_dir is None:
        data_dir = os.getenv("QUANT_DATA_DIR", "storage/quant/data_cybos")

    try:
        tickers = _resolve_batch_tickers()
    except Exception as e:
        return {"status": "error", "message": f"DB load failed: {e}"}

    if not tickers:
        logger.warning("퀀트 배치 처리할 종목이 DB에 없습니다.")
        return {"status": "ok", "message": "No tickers found", "success_count": 0}

    logger.info("퀀트 feature 배치 시작: %d 종목", len(tickers))

    success_count = 0
    failures = []

    for idx, ticker in enumerate(tickers):
        logger.info("[%d/%d] %s 퀀트 feature 처리 중...", idx + 1, len(tickers), ticker)
        try:
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
        except Exception as e:
            logger.error("  -> %s 퀀트 feature 처리 실패: %s", ticker, str(e))
            failures.append({"ticker": ticker, "error": str(e)})

    status = "ok" if not failures else "partial"
    result = {
        "status": status,
        "batch_type": "quant_feature",
        "total_tickers": len(tickers),
        "success_count": success_count,
        "failure_count": len(failures),
        "failures": failures,
        "completed_at": datetime.now().isoformat(),
    }
    logger.info("퀀트 feature 배치 완료: %d 성공, %d 실패 (status=%s)", success_count, len(failures), status)
    return result


def run_daily_batch_preparation(
    data_dir: Optional[str] = None,
    horizon_minutes: int = 5,
    feature_profile: str = "mtf",
    days: int = 730
) -> Dict[str, Any]:
    """
    기존 수동 전체 배치용 진입점:
    1) 뉴스/RAG 배치
    2) 퀀트 feature 배치
    """
    news_result = run_news_rag_batch()
    if news_result.get("status") != "ok":
        return news_result

    quant_result = run_quant_feature_batch(
        data_dir=data_dir,
        horizon_minutes=horizon_minutes,
        feature_profile=feature_profile,
        days=days,
    )
    if quant_result.get("status") != "ok":
        return quant_result

    result = {
        "status": "ok",
        "batch_type": "full",
        "news": news_result,
        "quant": quant_result,
        "completed_at": datetime.now().isoformat(),
    }
    logger.info("통합 배치 완료")
    return result
