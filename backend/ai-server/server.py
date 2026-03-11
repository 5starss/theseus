import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import Body, FastAPI, HTTPException, Query

from app.news.agent import NewsReporterAgent
from app.news.eval import RAGEvaluator
from app.quant.agent import QuantAnalysisAgent
from app.quant.pipeline import (
    extract_features_for_ticker,
    load_latest_global_model,
    resolve_tickers,
    run_adaptive_winrate_for_ticker,
    train_for_ticker,
    train_global_model,
)
from app.shared.rag.ingest_pipeline import RAGIngestPipeline
from app.shared.agents.judge_agent import JudgeAgent
from app.shared.rag.reranker import SolarReranker
from app.shared.rag.vector_db import NewsVectorDB
from app.shared.agents.rebuttal_agent import RebuttalAgent
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

QUANT_ANALYZE_DEFAULTS: Dict[str, Any] = {
    "run_fetch": False,
    "run_feature_extract": True,
    "run_train": True,
    "use_pretrained": True,
    "use_panel_model": True,
    "reuse_global_model": True,
    "train_global_if_missing": True,
    "dynamic_hold": True,
    "train_rows": 80000,
    "test_rows": 2000,
    "step_rows": 2000,
}


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


@app.post("/v1/news/analysis-card")
def news_analysis_card(
    ticker: str = Query(..., pattern=TICKER_PATTERN),
    query: str = Query(..., min_length=1),
    news_k: int = Query(15, ge=1, le=50),
    community_k: int = Query(2, ge=0, le=20),
    rerank_top_n: int = Query(5, ge=1, le=20),
) -> Dict[str, Any]:
    try:
        vdb = NewsVectorDB()
        news_candidates = vdb.hybrid_query(query_text=query, k=news_k, source_filter=SOURCE_NEWS)
        news_docs = _rerank_news_candidates(query=query, candidates=news_candidates, top_n=rerank_top_n)
        community_docs: List[Any] = []
        if community_k > 0:
            community_docs = vdb.hybrid_query(query_text=query, k=community_k, source_filter=SOURCE_COMMUNITY)

        card = NewsReporterAgent().generate_analysis_card(
            ticker=ticker,
            question=query,
            news_docs=news_docs,
            community_docs=community_docs,
        )
        return {
            "status": "ok",
            "analysis_card": card,
            "retrieved": {
                "news_candidates": len(news_candidates),
                "news_used": len(news_docs),
                "community_used": len(community_docs),
            },
            "generated_at": datetime.now().isoformat(),
        }
    except Exception as exc:
        logger.exception("Failed to run news analysis card")
        raise HTTPException(status_code=500, detail=f"News analysis card failed: {exc}") from exc


@app.post("/v1/agents/news/analyze")
def agents_news_analyze(
    ticker: str = Query(..., pattern=TICKER_PATTERN),
    query: str = Query(..., min_length=1),
    news_k: int = Query(15, ge=1, le=50),
    community_k: int = Query(2, ge=0, le=20),
    rerank_top_n: int = Query(5, ge=1, le=20),
) -> Dict[str, Any]:
    out = news_analysis_card(
        ticker=ticker,
        query=query,
        news_k=news_k,
        community_k=community_k,
        rerank_top_n=rerank_top_n,
    )
    normalized = _normalize_analysis_card(out.get("analysis_card", {}), agent="news", ticker=ticker)
    return {
        "status": out.get("status", "ok"),
        "agent": "news",
        "analysis_card": normalized,
        "meta": {
            "retrieved": out.get("retrieved", {}),
            "generated_at": out.get("generated_at"),
        },
    }


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


@app.post("/v1/quant/analysis-card")
def quant_analysis_card(
    ticker: str = Query(..., pattern=TICKER_PATTERN),
    run_fetch: bool = Query(False),
    run_feature_extract: bool = Query(True),
    run_train: bool = Query(True),
    use_pretrained: bool = Query(True),
    use_panel_model: bool = Query(True),
    reuse_global_model: bool = Query(True),
    train_global_if_missing: bool = Query(True),
    model_type: str = Query("ensemble", pattern=r"^(ensemble|linear)$"),
    dynamic_hold: bool = Query(True),
    train_rows: int = Query(80000, ge=1000),
    test_rows: int = Query(2000, ge=200),
    step_rows: int = Query(2000, ge=200),
    horizon_minutes: int = Query(5, ge=1, le=120),
    use_llm_interpretation: bool = Query(True),
    debug: bool = Query(False, description="true면 quant_evidence/raw_result 포함"),
    news_card_json: Optional[str] = Query(
        None,
        description="news analysis_card JSON 문자열(선택). 전달 시 quant LLM 해석에 함께 반영",
    ),
) -> Dict[str, Any]:
    try:
        global_artifact = None
        global_model_path: Optional[str] = None
        if use_panel_model:
            reused = False
            if reuse_global_model:
                try:
                    g_latest = load_latest_global_model()
                    global_artifact = g_latest["artifact"]
                    global_model_path = g_latest["model_path"]
                    reused = True
                except Exception:
                    logger.info("Quant analysis card: global model reuse miss, fallback train")
            if not reused:
                if not train_global_if_missing:
                    raise ValueError("공통 모델이 없고 train_global_if_missing=false 입니다.")
                g_out = train_global_model(
                    tickers=resolve_tickers(tickers=None, data_dir=QUANT_DATA_DIR),
                    data_dir=QUANT_DATA_DIR,
                    run_fetch=run_fetch,
                    run_feature_extract=run_feature_extract,
                    horizon_minutes=horizon_minutes,
                    model_type=model_type,
                )
                global_artifact = g_out["artifact"]
                global_model_path = g_out["model_path"]

        result = run_adaptive_winrate_for_ticker(
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
        evidence = _build_quant_evidence(ticker=ticker, result=result)
        card = _build_quant_analysis_card(ticker=ticker, result=result)
        if use_llm_interpretation:
            parsed_news: Optional[Dict[str, Any]] = None
            if news_card_json:
                try:
                    parsed_news = json.loads(news_card_json)
                except Exception:
                    parsed_news = None
            try:
                llm_card = QuantAnalysisAgent().generate_analysis_card(
                    ticker=ticker,
                    quant_evidence=evidence,
                    news_card=parsed_news,
                )
                card = _apply_quant_card_guards(llm_card, result)
            except Exception:
                logger.exception("Quant LLM interpretation failed, fallback to rule-based card")
        response: Dict[str, Any] = {"status": "ok", "analysis_card": card}
        if debug:
            response["quant_evidence"] = evidence
            response["raw_result"] = result
        return response
    except Exception as exc:
        logger.exception("Failed to run quant analysis card for %s", ticker)
        raise HTTPException(status_code=500, detail=f"Quant analysis card failed: {exc}") from exc


@app.post("/v1/agents/quant/analyze")
def agents_quant_analyze(
    ticker: str = Query(..., pattern=TICKER_PATTERN),
    model_type: str = Query("ensemble", pattern=r"^(ensemble|linear)$"),
    horizon_minutes: int = Query(5, ge=1, le=120),
    use_llm_interpretation: bool = Query(True),
    debug: bool = Query(False),
    news_card_json: Optional[str] = Query(None),
) -> Dict[str, Any]:
    out = quant_analysis_card(
        ticker=ticker,
        run_fetch=bool(QUANT_ANALYZE_DEFAULTS["run_fetch"]),
        run_feature_extract=bool(QUANT_ANALYZE_DEFAULTS["run_feature_extract"]),
        run_train=bool(QUANT_ANALYZE_DEFAULTS["run_train"]),
        use_pretrained=bool(QUANT_ANALYZE_DEFAULTS["use_pretrained"]),
        use_panel_model=bool(QUANT_ANALYZE_DEFAULTS["use_panel_model"]),
        reuse_global_model=bool(QUANT_ANALYZE_DEFAULTS["reuse_global_model"]),
        train_global_if_missing=bool(QUANT_ANALYZE_DEFAULTS["train_global_if_missing"]),
        model_type=model_type,
        dynamic_hold=bool(QUANT_ANALYZE_DEFAULTS["dynamic_hold"]),
        train_rows=int(QUANT_ANALYZE_DEFAULTS["train_rows"]),
        test_rows=int(QUANT_ANALYZE_DEFAULTS["test_rows"]),
        step_rows=int(QUANT_ANALYZE_DEFAULTS["step_rows"]),
        horizon_minutes=horizon_minutes,
        use_llm_interpretation=use_llm_interpretation,
        debug=debug,
        news_card_json=news_card_json,
    )
    meta = _build_quant_meta(out, debug=debug)
    normalized = _normalize_analysis_card(out.get("analysis_card", {}), agent="quant", ticker=ticker)
    return {
        "status": out.get("status", "ok"),
        "agent": "quant",
        "analysis_card": normalized,
        "meta": meta,
    }


@app.post("/v1/agents/rebuttal-once")
def agents_rebuttal_once(
    payload: Dict[str, Any] = Body(
        ...,
        example={
            "news_card": {"agent": "news", "score": 12},
            "quant_card": {"agent": "quant", "score": -8},
            "score_gap_threshold": 15,
            "enabled": True,
        },
    ),
) -> Dict[str, Any]:
    try:
        news_card = payload.get("news_card") or {}
        quant_card = payload.get("quant_card") or {}
        enabled = bool(payload.get("enabled", True))
        include_cards = bool(payload.get("include_cards", False))
        score_gap_threshold = int(payload.get("score_gap_threshold", 15))

        news_card = _normalize_analysis_card(news_card, agent="news", ticker=str(news_card.get("ticker", "")))
        quant_card = _normalize_analysis_card(quant_card, agent="quant", ticker=str(quant_card.get("ticker", "")))

        news_score = int(news_card.get("score", 0))
        quant_score = int(quant_card.get("score", 0))
        score_gap = abs(news_score - quant_score)
        triggered = enabled and (score_gap > score_gap_threshold)

        rebuttal = {"news_rebuttal": "", "quant_rebuttal": ""}
        if triggered:
            try:
                rebuttal = RebuttalAgent().generate_rebuttal(news_card=news_card, quant_card=quant_card)
            except Exception:
                logger.exception("Rebuttal generation failed, fallback empty rebuttal")
            rebuttal = _ensure_rebuttal_text(rebuttal, news_card, quant_card)

        response = {
            "status": "ok",
            "triggered": triggered,
            "rebuttal_round": 1 if triggered else 0,
            "score_gap": score_gap,
            "score_gap_threshold": score_gap_threshold,
            "rebuttal": rebuttal,
        }
        if include_cards:
            response["news_card"] = news_card
            response["quant_card"] = quant_card
        return response
    except Exception as exc:
        logger.exception("Failed to run one-shot rebuttal")
        raise HTTPException(status_code=500, detail=f"One-shot rebuttal failed: {exc}") from exc


@app.post("/v1/agents/analyze-with-rebuttal")
def agents_analyze_with_rebuttal(
    ticker: str = Query(..., pattern=TICKER_PATTERN),
    query: str = Query(..., min_length=1),
    model_type: str = Query("ensemble", pattern=r"^(ensemble|linear)$"),
    horizon_minutes: int = Query(5, ge=1, le=120),
    use_llm_interpretation: bool = Query(True),
    score_gap_threshold: int = Query(15, ge=1, le=60),
    rebuttal_enabled: bool = Query(True),
    debug: bool = Query(False),
) -> Dict[str, Any]:
    """
    News/Quant 분석 카드를 생성하고, 점수 충돌 시 1회 반박을 수행합니다.
    """
    try:
        news_out = agents_news_analyze(
            ticker=ticker,
            query=query,
            news_k=15,
            community_k=2,
            rerank_top_n=5,
        )
        news_card = news_out.get("analysis_card", {})

        quant_out = agents_quant_analyze(
            ticker=ticker,
            model_type=model_type,
            horizon_minutes=horizon_minutes,
            use_llm_interpretation=use_llm_interpretation,
            debug=debug,
            news_card_json=json.dumps(news_card, ensure_ascii=False),
        )
        quant_card = quant_out.get("analysis_card", {})

        rebuttal_payload = {
            "news_card": news_card,
            "quant_card": quant_card,
            "score_gap_threshold": score_gap_threshold,
            "enabled": rebuttal_enabled,
            "include_cards": debug,
        }
        rebuttal_out = agents_rebuttal_once(rebuttal_payload)

        return {
            "status": "ok",
            "ticker": ticker,
            "news": news_out,
            "quant": quant_out,
            "rebuttal": rebuttal_out,
        }
    except Exception as exc:
        logger.exception("Failed to run agents analyze-with-rebuttal")
        raise HTTPException(status_code=500, detail=f"Analyze with rebuttal failed: {exc}") from exc


@app.post("/v1/agents/judge/decide")
def agents_judge_decide(
    payload: Dict[str, Any] = Body(
        ...,
        example={
            "ticker": "005930",
            "current_price": 72300,
            "available_cash": 5000000,
            "risk_type": "moderate",
            "news_card": {"agent": "news", "score": 12, "confidence": 0.7},
            "quant_card": {"agent": "quant", "score": 4, "confidence": 0.6},
        },
    ),
) -> Dict[str, Any]:
    try:
        ticker = str(payload.get("ticker") or "000000")
        current_price = int(float(payload.get("current_price", 0)))
        available_cash = int(float(payload.get("available_cash", 0)))
        risk_type = str(payload.get("risk_type", "moderate"))
        news_card = _normalize_analysis_card(payload.get("news_card") or {}, agent="news", ticker=ticker)
        quant_card = _normalize_analysis_card(payload.get("quant_card") or {}, agent="quant", ticker=ticker)

        input_payload = {
            "ticker": ticker,
            "current_price": current_price,
            "available_cash": available_cash,
            "risk_type": risk_type,
            "news_card": news_card,
            "quant_card": quant_card,
        }

        try:
            order_card = JudgeAgent().generate_order_card(input_payload)
        except Exception:
            logger.exception("Judge LLM failed, fallback to rule-based decision")
            order_card = _fallback_judge_order(input_payload)

        return {"status": "ok", "order_card": order_card}
    except Exception as exc:
        logger.exception("Failed to run judge decision")
        raise HTTPException(status_code=500, detail=f"Judge decision failed: {exc}") from exc


@app.post("/v1/agents/full-decision")
def agents_full_decision(
    ticker: str = Query(..., pattern=TICKER_PATTERN),
    query: str = Query(..., min_length=1),
    current_price: int = Query(..., gt=0),
    available_cash: int = Query(..., ge=0),
    risk_type: str = Query("moderate", pattern=r"^(conservative|moderate|aggressive)$"),
    model_type: str = Query("ensemble", pattern=r"^(ensemble|linear)$"),
    horizon_minutes: int = Query(5, ge=1, le=120),
    use_llm_interpretation: bool = Query(True),
    score_gap_threshold: int = Query(15, ge=1, le=60),
    rebuttal_enabled: bool = Query(True),
    debug: bool = Query(False),
) -> Dict[str, Any]:
    """
    News/Quant 분석 -> 필요시 1회 반박 -> Judge 주문결정까지 한 번에 수행합니다.
    """
    try:
        analysis_out = agents_analyze_with_rebuttal(
            ticker=ticker,
            query=query,
            model_type=model_type,
            horizon_minutes=horizon_minutes,
            use_llm_interpretation=use_llm_interpretation,
            score_gap_threshold=score_gap_threshold,
            rebuttal_enabled=rebuttal_enabled,
            debug=debug,
        )
        news_card = analysis_out.get("news", {}).get("analysis_card", {})
        quant_card = analysis_out.get("quant", {}).get("analysis_card", {})
        rebuttal = analysis_out.get("rebuttal", {})

        judge_payload = {
            "ticker": ticker,
            "current_price": current_price,
            "available_cash": available_cash,
            "risk_type": risk_type,
            "news_card": news_card,
            "quant_card": quant_card,
            "rebuttal": rebuttal.get("rebuttal", {}),
        }
        judge_out = agents_judge_decide(judge_payload)

        return {
            "status": "ok",
            "ticker": ticker,
            "analysis": analysis_out,
            "judge": judge_out,
        }
    except Exception as exc:
        logger.exception("Failed to run full decision pipeline")
        raise HTTPException(status_code=500, detail=f"Full decision pipeline failed: {exc}") from exc


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


def _score_to_stance(score: int) -> str:
    if score >= 20:
        return "strong_buy"
    if score >= 10:
        return "buy"
    if score <= -20:
        return "strong_sell"
    if score <= -10:
        return "sell"
    return "hold"


def _build_quant_analysis_card(ticker: str, result: Dict[str, Any]) -> Dict[str, Any]:
    win_rate = float(result.get("win_rate", 0.0))
    trade_count = int(result.get("trade_count", 0))
    sharpe = float(result.get("sharpe", 0.0))
    cum_return = float(result.get("cum_return", 0.0))
    dir_acc = float(result.get("directional_accuracy_all", 0.0))
    dir_base = float(result.get("directional_baseline_all", 0.0))
    best = result.get("best_params", {}) or {}
    quality_flags = result.get("quality_flags", []) or []
    reliability_reasons = result.get("reliability_reasons", []) or []

    score_raw = int(round((win_rate - 0.5) * 100))
    score = score_raw

    # Directional quality penalty: 기준선 이하 성능이면 가중 패널티
    dir_gap = dir_base - dir_acc
    if dir_gap > 0:
        score -= 10 if dir_gap > 0.10 else 5

    score = max(-30, min(30, score))
    stance = _score_to_stance(score)

    sample_factor = min(1.0, trade_count / 500.0)
    confidence = 0.5 * max(0.0, min(1.0, win_rate)) + 0.5 * sample_factor
    if not result.get("is_reliable_for_llm", True):
        confidence *= 0.6

    # Confidence cap by quality flags
    if "LOW_SAMPLE_SIZE" in quality_flags:
        confidence = min(confidence, 0.45)
    if "LOW_EXPOSURE" in quality_flags:
        confidence = min(confidence, 0.35)

    # Hard guard: 표본 부족/신뢰도 저하면 Judge 입력을 hold 근처로 제한
    if trade_count < 20 or not result.get("is_reliable_for_llm", True):
        score = max(-3, min(3, score))
        stance = "hold"

    confidence = round(max(0.0, min(1.0, confidence)), 2)

    if trade_count < 20 or not result.get("is_reliable_for_llm", True):
        reasons = [
            f"저신뢰 표본(trades={trade_count})",
            f"dir_acc {dir_acc:.3f} < base {dir_base:.3f}",
            f"th {float(best.get('threshold', 0.0)):.6f} / hold {int(best.get('hold_bars', 0))}",
        ]
    else:
        reasons = [
            f"win {win_rate:.1%} / trades {trade_count}",
            f"ret {cum_return:.1%} / sharpe {sharpe:.2f}",
            f"th {float(best.get('threshold', 0.0)):.6f} / hold {int(best.get('hold_bars', 0))}",
        ]

    win_rate_signal = round((win_rate - 0.5) * 60, 2)
    risk_adjusted_signal = round(max(-10.0, min(10.0, sharpe / 2.0)), 2)
    sample_signal = round(sample_factor * 10.0, 2)
    if trade_count < 20 or not result.get("is_reliable_for_llm", True):
        win_rate_signal = round(max(-3.0, min(3.0, win_rate_signal)), 2)
        risk_adjusted_signal = round(max(-3.0, min(3.0, risk_adjusted_signal)), 2)
        sample_signal = round(max(0.0, min(3.0, sample_signal)), 2)

    return {
        "$schema": "analysis_card_v1",
        "agent": "quant",
        "ticker": ticker,
        "timestamp": _kst_now_iso(),
        "stance": stance,
        "confidence": confidence,
        "score": score,
        "signal_breakdown": {
            "win_rate_signal": win_rate_signal,
            "risk_adjusted_signal": risk_adjusted_signal,
            "sample_signal": sample_signal,
        },
        "top_reasons": reasons[:3],
        "risk_flags": quality_flags,
        "requested_action": {
            "preference": "adaptive_threshold_trade",
            "avoid_if": "low_reliability" if not result.get("is_reliable_for_llm", True) else "none",
            "threshold": float(best.get("threshold", 0.0)),
            "hold_bars": int(best.get("hold_bars", 0)),
            "cost_bps": float(best.get("cost_bps", 0.0)),
            "reliability_reason": quality_flags,
        },
        "model_meta": {
            "model_path": result.get("model_path"),
            "confidence_band": result.get("confidence_band"),
            "directional_accuracy_all": dir_acc,
            "directional_baseline_all": dir_base,
            "is_reliable_for_llm": bool(result.get("is_reliable_for_llm", True)),
            "reliability_reason": quality_flags,
            "reliability_reason_detail": reliability_reasons,
        },
    }


def _build_quant_evidence(ticker: str, result: Dict[str, Any]) -> Dict[str, Any]:
    best = result.get("best_params", {}) or {}
    return {
        "$schema": "quant_evidence_v1",
        "ticker": ticker,
        "as_of": _kst_now_iso(),
        "adaptive_params": {
            "threshold": float(best.get("threshold", 0.0)),
            "hold_bars": int(best.get("hold_bars", 0)),
            "cost_bps": float(best.get("cost_bps", 0.0)),
            "vol_scale": float(best.get("vol_scale", 0.0)),
            "baseline_vol": float(best.get("baseline_vol", 0.0)),
        },
        "backtest_core": {
            "win_rate": float(result.get("win_rate", 0.0)),
            "trade_count": int(result.get("trade_count", 0)),
            "cum_return": float(result.get("cum_return", 0.0)),
            "sharpe": float(result.get("sharpe", 0.0)),
        },
        "directional_quality": {
            "directional_accuracy_all": float(result.get("directional_accuracy_all", 0.0)),
            "directional_baseline_all": float(result.get("directional_baseline_all", 0.0)),
        },
        "reliability": {
            "confidence_band": result.get("confidence_band"),
            "is_reliable_for_llm": bool(result.get("is_reliable_for_llm", True)),
            "quality_flags": result.get("quality_flags", []) or [],
            "reliability_reasons": result.get("reliability_reasons", []) or [],
        },
        "model_meta": {"model_path": result.get("model_path")},
    }


def _apply_quant_card_guards(card: Dict[str, Any], result: Dict[str, Any]) -> Dict[str, Any]:
    trade_count = int(result.get("trade_count", 0))
    is_reliable = bool(result.get("is_reliable_for_llm", True))
    quality_flags = result.get("quality_flags", []) or []
    dir_acc = float(result.get("directional_accuracy_all", 0.0))
    dir_base = float(result.get("directional_baseline_all", 0.0))

    score = int(card.get("score", 0))
    confidence = float(card.get("confidence", 0.0))
    stance = str(card.get("stance", "hold"))
    valid_stances = {"strong_buy", "buy", "hold", "sell", "strong_sell"}
    if stance not in valid_stances:
        stance = "hold"

    if dir_acc < dir_base and stance in ("strong_buy", "strong_sell"):
        stance = "hold"
        score = max(-5, min(5, score))
    if trade_count < 20 or (not is_reliable):
        stance = "hold"
        score = max(-3, min(3, score))
        confidence = min(confidence, 0.35)
    if "LOW_SAMPLE_SIZE" in quality_flags:
        confidence = min(confidence, 0.45)
    if "LOW_EXPOSURE" in quality_flags:
        confidence = min(confidence, 0.35)

    card["$schema"] = "analysis_card_v1"
    card["agent"] = "quant"
    card["ticker"] = result.get("ticker", card.get("ticker"))
    card["timestamp"] = card.get("timestamp") or datetime.now().isoformat()
    card["stance"] = stance
    card["score"] = int(max(-30, min(30, score)))
    card["confidence"] = round(max(0.0, min(1.0, confidence)), 2)
    raw_reasons = card.get("top_reasons") or []
    if not isinstance(raw_reasons, list):
        raw_reasons = [str(raw_reasons)]
    card["top_reasons"] = [str(r) for r in raw_reasons[:3]]

    raw_flags = card.get("risk_flags") or []
    if not isinstance(raw_flags, list):
        raw_flags = [str(raw_flags)]
    card["risk_flags"] = list(dict.fromkeys([str(f) for f in raw_flags] + quality_flags))

    req_action = card.get("requested_action")
    if not isinstance(req_action, dict):
        req_action = {"preference": str(req_action) if req_action else "hold"}
    req_action.setdefault("avoid_if", "low_reliability" if not is_reliable else "none")
    card["requested_action"] = req_action

    sig = card.get("signal_breakdown")
    if not isinstance(sig, dict):
        card["signal_breakdown"] = {}

    model_meta = card.get("model_meta") or {}
    model_meta["model_path"] = result.get("model_path")
    model_meta["confidence_band"] = result.get("confidence_band")
    model_meta["directional_accuracy_all"] = dir_acc
    model_meta["directional_baseline_all"] = dir_base
    model_meta["is_reliable_for_llm"] = is_reliable
    card["model_meta"] = model_meta
    return card


KST = timezone(timedelta(hours=9))


def _kst_now_iso() -> str:
    return datetime.now(KST).isoformat()


def _to_kst_iso(value: Any) -> str:
    if value is None:
        return _kst_now_iso()
    try:
        s = str(value).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=KST)
        return dt.astimezone(KST).isoformat()
    except Exception:
        return _kst_now_iso()


def _normalize_analysis_card(card: Dict[str, Any], agent: str, ticker: str) -> Dict[str, Any]:
    score = int(card.get("score", 0))
    score = max(-30, min(30, score))
    confidence = float(card.get("confidence", 0.0))
    confidence = round(max(0.0, min(1.0, confidence)), 2)

    stance = str(card.get("stance", "hold"))
    valid_stances = {"strong_buy", "buy", "hold", "sell", "strong_sell"}
    if stance not in valid_stances:
        stance = _score_to_stance(score)

    raw_breakdown = card.get("signal_breakdown")
    signal_breakdown: Dict[str, Any] = {}
    if isinstance(raw_breakdown, dict):
        for k, v in raw_breakdown.items():
            try:
                signal_breakdown[str(k)] = float(v)
            except Exception:
                continue

    raw_reasons = card.get("top_reasons") or []
    if not isinstance(raw_reasons, list):
        raw_reasons = [str(raw_reasons)]
    top_reasons = [str(x) for x in raw_reasons[:3]]

    raw_flags = card.get("risk_flags") or []
    if not isinstance(raw_flags, list):
        raw_flags = [str(raw_flags)]
    risk_flags = list(dict.fromkeys([str(x) for x in raw_flags]))

    requested_action = card.get("requested_action")
    if not isinstance(requested_action, dict):
        requested_action = {"preference": str(requested_action) if requested_action else "hold"}

    normalized = {
        "$schema": "analysis_card_v1",
        "agent": agent,
        "ticker": ticker or str(card.get("ticker", "")),
        "timestamp": _to_kst_iso(card.get("timestamp")),
        "stance": stance,
        "confidence": confidence,
        "score": score,
        "signal_breakdown": signal_breakdown,
        "top_reasons": top_reasons,
        "risk_flags": risk_flags,
        "requested_action": requested_action,
    }
    if isinstance(card.get("model_meta"), dict):
        normalized["model_meta"] = card["model_meta"]
    return normalized


def _ensure_rebuttal_text(rebuttal: Dict[str, str], news_card: Dict[str, Any], quant_card: Dict[str, Any]) -> Dict[str, str]:
    news_text = str(rebuttal.get("news_rebuttal", "")).strip()
    quant_text = str(rebuttal.get("quant_rebuttal", "")).strip()
    if not news_text:
        q_flags = ",".join((quant_card.get("risk_flags") or [])[:2])
        news_text = f"Quant는 {q_flags or '리스크'}가 있어 보수 해석이 필요합니다."
    if not quant_text:
        n_conf = float(news_card.get("confidence", 0.0))
        quant_text = (
            "News는 단기 모멘텀 반영이 커서 가격 신호 확인이 필요합니다."
            if n_conf >= 0.7
            else "News 근거의 강도가 제한적이므로 정량 신호 병행이 필요합니다."
        )
    return {"news_rebuttal": news_text[:200], "quant_rebuttal": quant_text[:200]}


def _build_quant_meta(out: Dict[str, Any], debug: bool) -> Dict[str, Any]:
    meta: Dict[str, Any] = {"debug": debug}
    if debug:
        meta["quant_evidence"] = out.get("quant_evidence")
        meta["raw_result"] = out.get("raw_result")
    return meta


def _fallback_judge_order(payload: Dict[str, Any]) -> Dict[str, Any]:
    ticker = str(payload.get("ticker", "000000"))
    price = int(float(payload.get("current_price", 0)))
    cash = int(float(payload.get("available_cash", 0)))
    risk_type = str(payload.get("risk_type", "moderate"))
    news = payload.get("news_card", {})
    quant = payload.get("quant_card", {})

    news_score = int(news.get("score", 0))
    quant_score = int(quant.get("score", 0))
    final_score = int(round(0.5 * news_score + 0.5 * quant_score))
    final_score = max(-30, min(30, final_score))

    if final_score >= 15:
        action, stance = "buy", "strong_buy"
    elif final_score >= 8:
        action, stance = "buy", "buy"
    elif final_score <= -15:
        action, stance = "sell", "strong_sell"
    elif final_score <= -8:
        action, stance = "sell", "sell"
    else:
        action, stance = "hold", "hold"

    risk_map = {"conservative": 0.10, "moderate": 0.20, "aggressive": 0.35}
    base_pct = risk_map.get(risk_type, 0.20)
    intensity = min(1.0, abs(final_score) / 30.0)
    target_value = int(cash * base_pct * intensity)
    quantity = int(target_value / price) if price > 0 and action != "hold" else 0
    quantity = max(0, quantity)

    stop_loss = int(price * 0.985) if price > 0 else 0
    take_profit = int(price * 1.05) if price > 0 else 0
    return {
        "$schema": "order_card_v1",
        "ticker": ticker,
        "timestamp": _kst_now_iso(),
        "final_stance": stance,
        "final_score": final_score,
        "order": {
            "action": action,
            "order_type": "limit",
            "price": price,
            "quantity": quantity if action != "hold" else 0,
            "time_in_force": "day",
        },
        "risk_management": {
            "stop_loss_price": stop_loss,
            "take_profit_price": take_profit,
        },
        "verdict": "News/Quant 점수 가중 합 기반 기본 의사결정",
    }


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
