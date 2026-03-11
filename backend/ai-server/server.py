import json
import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query

from app.news.agent import NewsReporterAgent
from app.news.eval import RAGEvaluator
from app.quant.pipeline import (
    extract_features_for_ticker,
    load_latest_global_model,
    resolve_tickers,
    run_adaptive_winrate_for_ticker,
    train_for_ticker,
    train_global_model,
)
from app.shared.rag.ingest_pipeline import RAGIngestPipeline
from app.shared.rag.reranker import SolarReranker
from app.shared.rag.vector_db import NewsVectorDB
from collector.kis_news import fetch_kis_news_title
from collector.storage import get_storage_dir, list_storage_files, save_snapshot
from collector.toss_community import fetch_toss_community_comments

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="AI Server Infrastructure Base")
TICKER_PATTERN = r"^\d{6}$"
SOURCE_NEWS = "KIS_NEWS"
SOURCE_COMMUNITY = "TOSS_COMMUNITY"
DEFAULT_QUANT_DATA_DIR = os.path.join(get_storage_dir("quant"), "data_cybos")
QUANT_DATA_DIR = os.getenv("QUANT_DATA_DIR", DEFAULT_QUANT_DATA_DIR)


@app.get("/health")
def health_check():
    return {"status": "healthy", "message": "AI Server is running"}


@app.get("/v1/test")
def test_connection():
    return {"message": "Connection to AI Server successful"}


@app.get("/v1/collect/news")
def collect_news(ticker: str = Query(..., pattern=TICKER_PATTERN)) -> Dict[str, Any]:
    return _collect_news_result(ticker)


@app.get("/v1/collect/community")
def collect_community(
    ticker: str = Query(..., pattern=TICKER_PATTERN),
    limit: int = Query(15, ge=1, le=100),
    community_limit: Optional[int] = Query(None, ge=1, le=100),
) -> Dict[str, Any]:
    resolved_limit = community_limit if community_limit is not None else limit
    return _collect_community_result(ticker=ticker, limit=resolved_limit)


@app.get("/v1/collect/all")
def collect_all(
    ticker: str = Query(..., pattern=TICKER_PATTERN),
    community_limit: int = Query(15, ge=1, le=100),
) -> Dict[str, Any]:
    news_result = _collect_news_result(ticker)
    community_result = _collect_community_result(ticker=ticker, limit=community_limit)
    return {
        "ticker": ticker,
        "news": news_result,
        "community": community_result,
    }


@app.get("/v1/storage/status")
def storage_status(
    category: str = Query("news", pattern=r"^(news|quant)$"),
    limit: int = Query(20, ge=1, le=200),
) -> Dict[str, Any]:
    try:
        return list_storage_files(category=category, limit=limit)
    except Exception as exc:
        logger.exception("Failed to read storage status")
        raise HTTPException(status_code=500, detail=f"Storage status failed: {exc}") from exc


@app.post("/v1/rag/ingest")
def rag_ingest(
    ticker: str = Query(..., pattern=TICKER_PATTERN),
    community_limit: int = Query(15, ge=1, le=100),
    reset_collection: bool = Query(True),
) -> Dict[str, Any]:
    try:
        pipeline = RAGIngestPipeline()
        result = pipeline.run(
            ticker=ticker,
            community_limit=community_limit,
            reset_collection=reset_collection,
        )
        return {"status": "ok", "result": result.to_dict()}
    except Exception as exc:
        logger.exception("Failed to run sequential RAG ingest for %s", ticker)
        raise HTTPException(status_code=500, detail=f"RAG ingest failed: {exc}") from exc


@app.post("/v1/rag/chat")
def rag_chat(
    query: str = Query(..., min_length=1),
    news_k: int = Query(15, ge=1, le=50),
    community_k: int = Query(2, ge=0, le=20),
    rerank_top_n: int = Query(5, ge=1, le=20),
    with_eval: bool = Query(False),
) -> Dict[str, Any]:
    try:
        return _run_rag_chat_pipeline(
            query=query,
            news_k=news_k,
            community_k=community_k,
            rerank_top_n=rerank_top_n,
            with_eval=with_eval,
        )
    except Exception as exc:
        logger.exception("Failed to run RAG chat")
        raise HTTPException(status_code=500, detail=f"RAG chat failed: {exc}") from exc


@app.post("/v1/quant/feature-extract")
def quant_feature_extract(
    ticker: str = Query(..., pattern=TICKER_PATTERN),
    run_fetch: bool = Query(True),
    horizon_minutes: int = Query(5, ge=1, le=120),
) -> Dict[str, Any]:
    try:
        out = extract_features_for_ticker(
            ticker=ticker,
            data_dir=QUANT_DATA_DIR,
            run_fetch=run_fetch,
            horizon_minutes=horizon_minutes,
        )
        return {
            "status": "ok",
            "ticker": ticker,
            "storage_dir": out["storage_dir"],
            "raw_path": out["raw_path"],
            "feature_path": out["feature_path"],
            "feature_rows": out["feature_rows"],
            "feature_columns": out["feature_columns"],
            "meta_path": out["meta_path"],
        }
    except Exception as exc:
        logger.exception("Failed to run quant feature extraction for %s", ticker)
        raise HTTPException(status_code=500, detail=f"Quant feature extraction failed: {exc}") from exc


@app.post("/v1/quant/train")
def quant_train(
    ticker: str = Query(..., pattern=TICKER_PATTERN),
    run_fetch: bool = Query(True),
    run_feature_extract: bool = Query(True),
    horizon_minutes: int = Query(5, ge=1, le=120),
    model_type: str = Query("ensemble", pattern=r"^(ensemble|linear)$"),
) -> Dict[str, Any]:
    """1분봉 raw -> feature -> model 학습을 ai-server/quant 내부 로직으로 수행합니다."""
    try:
        out = train_for_ticker(
            ticker=ticker,
            data_dir=QUANT_DATA_DIR,
            run_fetch=run_fetch,
            run_feature_extract=run_feature_extract,
            horizon_minutes=horizon_minutes,
            model_type=model_type,
        )
        return {
            "status": "ok",
            "ticker": ticker,
            "model_type": model_type,
            "storage_dir": out["storage_dir"],
            "raw_path": out["raw_path"],
            "feature_path": out["feature_path"],
            "model_path": out["model_path"],
            "metrics": out["metrics"],
            "feature_count": out["feature_count"],
            "feature_names": out["feature_names"],
            "threshold": out["threshold"],
        }
    except Exception as exc:
        logger.exception("Failed to run quant train for %s", ticker)
        raise HTTPException(status_code=500, detail=f"Quant train failed: {exc}") from exc


@app.post("/v1/quant/train-global")
def quant_train_global(
    tickers: Optional[str] = Query(None, description="콤마 구분 종목코드. 미지정 시 data_dir 전체"),
    run_fetch: bool = Query(True),
    run_feature_extract: bool = Query(True),
    horizon_minutes: int = Query(5, ge=1, le=120),
    model_type: str = Query("ensemble", pattern=r"^(ensemble|linear)$"),
) -> Dict[str, Any]:
    try:
        ticker_list = resolve_tickers(tickers=tickers, data_dir=QUANT_DATA_DIR)
        if not ticker_list:
            raise ValueError("처리할 종목이 없습니다.")

        out = train_global_model(
            tickers=ticker_list,
            data_dir=QUANT_DATA_DIR,
            run_fetch=run_fetch,
            run_feature_extract=run_feature_extract,
            horizon_minutes=horizon_minutes,
            model_type=model_type,
        )
        return {
            "status": "ok",
            "mode": "trained",
            "model_type": model_type,
            "tickers": out["tickers"],
            "rows_total": out["rows_total"],
            "feature_count": out["feature_count"],
            "metrics": out["metrics"],
            "model_path": out["model_path"],
        }
    except Exception as exc:
        logger.exception("Failed to run quant global train")
        raise HTTPException(status_code=500, detail=f"Quant global train failed: {exc}") from exc


@app.post("/v1/quant/adaptive-winrate")
def quant_adaptive_winrate(
    tickers: Optional[str] = Query(None, description="콤마 구분 종목코드. 미지정 시 data_dir 전체"),
    run_fetch: bool = Query(True),
    run_feature_extract: bool = Query(True),
    run_train: bool = Query(True),
    use_pretrained: bool = Query(True),
    use_panel_model: bool = Query(True, description="여러 종목 통합 학습 모델 사용 여부"),
    reuse_global_model: bool = Query(True, description="저장된 공통 모델 우선 재사용 여부"),
    train_global_if_missing: bool = Query(True, description="공통 모델 미존재 시 자동 학습 여부"),
    model_type: str = Query("ensemble", pattern=r"^(ensemble|linear)$"),
    dynamic_hold: bool = Query(True),
    train_rows: int = Query(80000, ge=1000),
    test_rows: int = Query(2000, ge=200),
    step_rows: int = Query(2000, ge=200),
    horizon_minutes: int = Query(5, ge=1, le=120),
) -> Dict[str, Any]:
    """
    종목별 adaptive threshold 최적화 및 백테스트를 수행해 승률(win_rate)을 산출합니다.
    LLM 호출 없이 quant 파이프라인 계산까지만 수행합니다.
    """
    try:
        ticker_list = resolve_tickers(tickers=tickers, data_dir=QUANT_DATA_DIR)
        if not ticker_list:
            raise ValueError("처리할 종목이 없습니다.")

        results: List[Dict[str, Any]] = []
        failures: List[Dict[str, str]] = []

        global_artifact = None
        global_model_path: Optional[str] = None
        global_training_info: Optional[Dict[str, Any]] = None
        if use_panel_model:
            reused = False
            if reuse_global_model:
                try:
                    g_latest = load_latest_global_model()
                    global_artifact = g_latest["artifact"]
                    global_model_path = g_latest["model_path"]
                    global_training_info = {
                        "mode": "reused",
                        "model_path": global_model_path,
                        "metrics": global_artifact.metrics,
                    }
                    reused = True
                    logger.info("  [Global] 기존 공통 모델 재사용: %s", global_model_path)
                except Exception:
                    logger.info("  [Global] 재사용 가능한 공통 모델이 없어 새로 학습합니다.")

            if not reused:
                if not train_global_if_missing:
                    raise ValueError("공통 모델이 없고 train_global_if_missing=false 입니다.")
                logger.info("  [Global] %d종목 통합 공통 모델(Panel Model) 학습 시작...", len(ticker_list))
                g_out = train_global_model(
                    tickers=ticker_list,
                    data_dir=QUANT_DATA_DIR,
                    run_fetch=run_fetch,
                    run_feature_extract=run_feature_extract,
                    horizon_minutes=horizon_minutes,
                    model_type=model_type,
                )
                global_artifact = g_out["artifact"]
                global_model_path = g_out["model_path"]
                global_training_info = {
                    "mode": "trained",
                    "tickers": g_out["tickers"],
                    "rows_total": g_out["rows_total"],
                    "model_path": global_model_path,
                    "metrics": g_out["metrics"],
                }
                logger.info("  [Global] 공통 모델 학습 완료 (정확도: %.4f)", global_artifact.metrics.get("directional_accuracy", 0.0))

        for ticker in ticker_list:
            try:
                results.append(
                    run_adaptive_winrate_for_ticker(
                        ticker=ticker,
                        data_dir=QUANT_DATA_DIR,
                        run_fetch=run_fetch,
                        run_feature_extract=run_feature_extract,
                        run_train=run_train,
                        use_pretrained=use_pretrained,
                        model_type=model_type,
                        dynamic_hold=dynamic_hold,
                        train_rows=train_rows,
                        test_rows=test_rows,
                        step_rows=step_rows,
                        horizon_minutes=horizon_minutes,
                        global_artifact=global_artifact,
                        global_model_path=global_model_path,
                    )
                )
            except Exception as ticker_exc:
                logger.exception("Adaptive winrate 처리 실패: %s", ticker)
                failures.append({"ticker": ticker, "error": str(ticker_exc)})

        return {
            "status": "ok",
            "model_type": model_type,
            "dynamic_hold": dynamic_hold,
            "tickers_total": len(ticker_list),
            "success_count": len(results),
            "failure_count": len(failures),
            "global_model": global_training_info,
            "results": results,
            "failures": failures,
        }
    except Exception as exc:
        logger.exception("Failed to run quant adaptive winrate pipeline")
        raise HTTPException(status_code=500, detail=f"Quant adaptive winrate failed: {exc}") from exc


def _run_rag_chat_pipeline(
    query: str,
    news_k: int,
    community_k: int,
    rerank_top_n: int,
    with_eval: bool,
) -> Dict[str, Any]:
    vdb = NewsVectorDB()

    news_candidates = vdb.hybrid_query(query_text=query, k=news_k, source_filter=SOURCE_NEWS)
    news_docs = _rerank_news_candidates(query=query, candidates=news_candidates, top_n=rerank_top_n)

    community_docs: List[Any] = []
    if community_k > 0:
        community_docs = vdb.hybrid_query(query_text=query, k=community_k, source_filter=SOURCE_COMMUNITY)

    agent = NewsReporterAgent()
    answer = agent.generate_response(question=query, news_docs=news_docs, community_docs=community_docs)

    eval_result = None
    if with_eval and (news_docs or community_docs):
        evaluator = RAGEvaluator()
        eval_result = evaluator.run_full_eval(
            question=query,
            response=answer,
            retrieved_docs=(news_docs + community_docs),
        )

    result = {
        "status": "ok",
        "query": query,
        "retrieved": {
            "news_candidates": len(news_candidates),
            "news_used": len(news_docs),
            "community_used": len(community_docs),
        },
        "answer": answer,
    }
    if eval_result is not None:
        result["eval"] = eval_result
    return result


def _rerank_news_candidates(query: str, candidates: List[Any], top_n: int) -> List[Any]:
    if not candidates:
        return []
    reranker = SolarReranker()
    return reranker.rerank(query=query, documents=candidates, top_n=top_n)


def _build_collect_payload(ticker: str, source_key: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "ticker": ticker,
        "collected_at": datetime.now().isoformat(),
        "sources": {source_key: items},
    }


def _build_collect_response(
    ticker: str,
    source: str,
    file_path: str,
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "ticker": ticker,
        "source": source,
        "count": len(items),
        "file_path": file_path,
        "data": items,
    }


def _collect_news_result(ticker: str) -> Dict[str, Any]:
    try:
        news_list = fetch_kis_news_title(ticker)
        payload = _build_collect_payload(ticker=ticker, source_key="news", items=news_list)
        file_path = save_snapshot("raw", ticker, payload)
        logger.info("Saved KIS news snapshot: ticker=%s count=%s path=%s", ticker, len(news_list), file_path)
        return _build_collect_response(
            ticker=ticker,
            source=SOURCE_NEWS,
            file_path=file_path,
            items=news_list,
        )
    except Exception as exc:
        logger.exception("Failed to collect KIS news for %s", ticker)
        raise HTTPException(status_code=500, detail=f"KIS news collection failed: {exc}") from exc


def _collect_community_result(ticker: str, limit: int) -> Dict[str, Any]:
    try:
        comments = fetch_toss_community_comments(ticker=ticker, limit=limit)
        payload = _build_collect_payload(ticker=ticker, source_key="community", items=comments)
        file_path = save_snapshot("comm", ticker, payload)
        logger.info(
            "Saved Toss community snapshot: ticker=%s count=%s limit=%s path=%s",
            ticker,
            len(comments),
            limit,
            file_path,
        )
        return _build_collect_response(
            ticker=ticker,
            source=SOURCE_COMMUNITY,
            file_path=file_path,
            items=comments,
        )
    except Exception as exc:
        logger.exception("Failed to collect Toss community for %s", ticker)
        raise HTTPException(status_code=500, detail=f"Toss community collection failed: {exc}") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
