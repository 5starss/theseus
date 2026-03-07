import argparse
import logging
import os
import sys
import time
from app.sources import fetch_and_store_news, convert_to_documents
from app.sources_community import fetch_and_store_community, convert_community_to_documents
from app.rag.vector_db import NewsVectorDB
from app.rag.ingest_pipeline import RAGIngestPipeline
from app.rag.reranker import SolarReranker
from app.agent.llm_agent import NewsReporterAgent
from app.eval.judge import RAGEvaluator

# 로깅 설정: 프로그램의 전체적인 흐름(수집, 색인, 대화 등)을 터미널에 실시간으로 표시합니다.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)] # 터미널(표준 출력)로 로그를 보냅니다.
)
logger = logging.getLogger(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def _log_duration(label: str, start_ts: float) -> float:
    """특정 작업의 경과 시간을 초 단위로 로깅합니다."""
    elapsed = time.perf_counter() - start_ts
    logger.info(f"[시간] {label}: {elapsed:.2f}초")
    return elapsed

def main():
    """
    이 프로그램의 '관제 센터' 역할을 합니다. 
    터미널 명령어(fetch, index, chat)에 따라 적절한 모듈을 호출하여 전체 작업을 조율합니다.
    """
    # 명령행 인자(Arguments)를 처리하기 위한 파서(Parser)를 설정합니다.
    parser = argparse.ArgumentParser(description="KIS 뉴스 기반 RAG AI 에이전트 CLI")
    # '모드(mode)'는 필수 인자이며, 다음 3가지 중 하나를 선택해야 합니다.
    parser.add_argument("mode", choices=["fetch", "index", "ingest", "chat"], help="실행 모드 (수집, 색인, 순차수집+색인, 대화)")
    # '종목코드(ticker)'는 기본값으로 삼성전자(005930)를 가집니다.
    parser.add_argument("--ticker", default="005930", help="분석할 종목코드 (기본: 005930)")
    # '질문(query)'은 AI에게 물어볼 내용을 담습니다.
    parser.add_argument("--query", help="AI 에이전트에게 보낼 질문 내용 (chat 모드 시 필수)")
    # 정량적 평가 수행 여부 옵션 추가
    parser.add_argument("--with-eval", action="store_true", help="답변 생성 후 정량적 품질 평가 수행")
    
    # 터미널에서 입력받은 인자들을 분석(Parsing)합니다.
    args = parser.parse_args()
    
    mode_start_ts = time.perf_counter()

    if args.mode == "fetch":
        logger.info(f"[{args.ticker}] 종목에 대한 최신 뉴스 수집을 시작합니다...")
        step_start_ts = time.perf_counter()
        raw_path = fetch_and_store_news(args.ticker)
        _log_duration("뉴스 수집(fetch_and_store_news)", step_start_ts)
        logger.info(f"뉴스 수집 완료! 원천 데이터 저장 경로: {raw_path}")
        
        logger.info(f"[{args.ticker}] 종목에 대한 토스증권 커뮤니티 데이터 수집을 시작합니다...")
        step_start_ts = time.perf_counter()
        comm_path = fetch_and_store_community(args.ticker)
        _log_duration("커뮤니티 수집(fetch_and_store_community)", step_start_ts)
        logger.info(f"커뮤니티 수집 완료! 원천 데이터 저장 경로: {comm_path}")
        _log_duration("fetch 모드 총 소요", mode_start_ts)
        
    # 2. ［색인 모드］: 수집된 원천 데이터를 벡터 DB(ChromaDB)에 숫자로 변환하여 저장합니다.
    elif args.mode == "index":
        logger.info("최근 수집된 뉴스 데이터를 벡터 DB에 색인(Indexing)하는 과정을 시작합니다...")
        # 'storage' 폴더에서 해당 종목의 가장 최신 뉴스 파일을 자동으로 찾아냅니다.
        storage_dir = os.path.join(BASE_DIR, "storage")
        if not os.path.exists(storage_dir):
            logger.error("storage 폴더가 존재하지 않습니다. 먼저 'fetch' 모드로 데이터를 수집하세요.")
            return
            
        candidate_files = [f for f in os.listdir(storage_dir) if f.startswith(f"raw_{args.ticker}_") and f.endswith(".json")]
        if not candidate_files:
            logger.error(f"{args.ticker}에 대한 수집 데이터가 없습니다. 먼저 'fetch' 모드를 실행하세요.")
            return
            
        # 가장 최근에 생성된 파일(알파벳순 마지막)을 선택합니다.
        latest_file = sorted(candidate_files)[-1]
        raw_path = os.path.join(storage_dir, latest_file)
        
        logger.info(f"색인 대상 파일이 확인되었습니다: {raw_path}")
        # JSON 원본 데이터를 AI 전용 문서 규격(Document)으로 정규화합니다.
        step_start_ts = time.perf_counter()
        docs = convert_to_documents(raw_path)
        _log_duration("뉴스 문서 변환(convert_to_documents)", step_start_ts)
        
        # 커뮤니티 데이터도 함께 색인
        comm_files = [f for f in os.listdir(storage_dir) if f.startswith(f"comm_{args.ticker}_") and f.endswith(".json")]
        if comm_files:
            latest_comm_file = sorted(comm_files)[-1]
            comm_path = os.path.join(storage_dir, latest_comm_file)
            logger.info(f"커뮤니티 색인 대상 파일이 확인되었습니다: {comm_path}")
            step_start_ts = time.perf_counter()
            comm_docs = convert_community_to_documents(comm_path)
            _log_duration("커뮤니티 문서 변환(convert_community_to_documents)", step_start_ts)
            docs.extend(comm_docs)
        
        if not docs:
            logger.error(f"'{raw_path}'에서 색인할 뉴스나 커뮤니티 데이터를 찾지 못했습니다. 뉴스 수집(fetch) 시 오류가 없었는지 확인하세요.")
            return
            
        logger.info(f"뉴스 및 커뮤니티 총 {len(docs)}건의 데이터를 벡터 DB에 저장합니다...")
        
        # 벡터 DB 인스턴스를 생성하고, 기존 데이터를 초기화한 뒤 새로 색인합니다.
        # (동일 데이터의 중복 색인을 방지합니다)
        step_start_ts = time.perf_counter()
        vdb = NewsVectorDB()
        _log_duration("벡터 DB 초기화(NewsVectorDB)", step_start_ts)

        step_start_ts = time.perf_counter()
        vdb.delete_collection()
        _log_duration("기존 컬렉션 초기화(delete_collection)", step_start_ts)

        step_start_ts = time.perf_counter()
        vdb.add_documents(docs)
        _log_duration("문서 색인(add_documents)", step_start_ts)
        logger.info("모든 문서가 성공적으로 색인되었습니다. 이제 'chat' 기능을 사용할 수 있습니다.")
        _log_duration("index 모드 총 소요", mode_start_ts)
        
    # 3. [순차 이식 모드] 수집 -> 문서 변환 -> 임베딩/저장까지 한 번에 수행
    elif args.mode == "ingest":
        logger.info(f"[{args.ticker}] 순차 RAG 이식 파이프라인 시작 (fetch -> embed/store)")
        step_start_ts = time.perf_counter()
        pipeline = RAGIngestPipeline(reset_collection=True)
        _log_duration("파이프라인 초기화(RAGIngestPipeline)", step_start_ts)

        step_start_ts = time.perf_counter()
        result = pipeline.run(args.ticker)
        _log_duration("순차 수집+색인(run)", step_start_ts)
        logger.info(
            f"순차 이식 완료: ticker={result.ticker}, "
            f"news={result.news_count}, community={result.community_count}, indexed={result.indexed_count}"
        )
        _log_duration("ingest 모드 총 소요", mode_start_ts)

    # 4. ［대화 모드］: 고도화된 하이브리드 검색 및 리랭킹 파이프라인을 실행합니다.
    elif args.mode == "chat":
        if not args.query:
            logger.error("'chat' 모드에서는 반드시 --query 옵션으로 질문 내용을 입력해야 합니다.")
            return
            
        logger.info(f"사용자의 질문 분석 및 고도화 검색 시작: '{args.query}'")
        
        step_start_ts = time.perf_counter()
        vdb = NewsVectorDB()
        _log_duration("벡터 DB 로드(NewsVectorDB)", step_start_ts)
        
        # ============================================================
        # [Track 1] 뉴스 전용 검색 → 리랭킹 → 상위 5건 (핵심 분석 근거)
        # ============================================================
        step_start_ts = time.perf_counter()
        news_candidates = vdb.hybrid_query(args.query, k=15, source_filter="KIS_NEWS")
        _log_duration("뉴스 하이브리드 검색(hybrid_query/KIS_NEWS)", step_start_ts)
        
        if not news_candidates:
            logger.warning("뉴스 데이터를 찾지 못했습니다.")
            news_docs = []
        else:
            logger.info(f"뉴스 {len(news_candidates)}건 후보에 대해 리랭킹 수행...")
            step_start_ts = time.perf_counter()
            reranker = SolarReranker()
            news_docs = reranker.rerank(args.query, news_candidates, top_n=5)
            _log_duration("뉴스 리랭킹(rerank)", step_start_ts)
        
        # ============================================================
        # [Track 2] 커뮤니티 전용 검색 → 상위 2건 (여론 참고용, 리랭킹 생략)
        # ============================================================
        step_start_ts = time.perf_counter()
        community_docs = vdb.hybrid_query(args.query, k=2, source_filter="TOSS_COMMUNITY")
        _log_duration("커뮤니티 하이브리드 검색(hybrid_query/TOSS_COMMUNITY)", step_start_ts)
        
        # [디버그] 2-Track 검색 결과 요약 로그
        logger.info("=" * 50)
        logger.info(f"[2-Track 검색 결과] 뉴스: {len(news_docs)}건 | 커뮤니티: {len(community_docs)}건")
        for i, doc in enumerate(news_docs):
            score = doc.metadata.get('rerank_score', '-')
            preview = doc.page_content[:40].replace('\n', ' ')
            logger.info(f"  뉴스 #{i+1} 점수={score} | {preview}...")
        for i, doc in enumerate(community_docs):
            preview = doc.page_content[:40].replace('\n', ' ')
            logger.info(f"  커뮤 #{i+1} | {preview}...")
        logger.info("=" * 50)
        
        # 모든 문서 병합 (eval용)
        retrieved_docs = news_docs + community_docs
        
        # [단계 3] 에이전트 답변 생성: 뉴스(메인) + 커뮤니티(보조) 분리 전달
        step_start_ts = time.perf_counter()
        agent = NewsReporterAgent()
        response = agent.generate_response(args.query, news_docs, community_docs)
        _log_duration("답변 생성(generate_response)", step_start_ts)
        
        # 최종 결과를 터미널에 보기 좋게 출력합니다.
        print("\n" + "★" + "="*60 + "★")
        print(f"  [AI 주식 전망 예측 에이전트 - 고도화 답변]")
        print("-" * 62)
        print(response)
        print("★" + "="*60 + "★" + "\n")

        # [단계 4] 정량적 평가 (옵션): 생성된 답변의 품질을 LLM이 스스로 채점합니다.
        if args.with_eval and retrieved_docs:
            logger.info("정량적 답변 품질 평가(LLM-as-a-Judge)를 수행 중입니다...")
            step_start_ts = time.perf_counter()
            evaluator = RAGEvaluator()
            eval_results = evaluator.run_full_eval(args.query, response, retrieved_docs)
            _log_duration("정량 평가(run_full_eval)", step_start_ts)
            
            print("  [AI 정량적 품질 평가 결과]")
            print(f"  - 신뢰성 (Faithfulness): {eval_results['faithfulness']['score']:.2f}")
            print(f"    ㄴ 근거: {eval_results['faithfulness']['reason']}")
            print(f"  - 답변 적절성 (Relevancy): {eval_results['relevancy']['score']:.2f}")
            print(f"    ㄴ 근거: {eval_results['relevancy']['reason']}")
            print("="*62 + "\n")

        _log_duration("chat 모드 총 소요", mode_start_ts)

if __name__ == "__main__":
    # 이 파일이 직접 실행될 때만 main() 함수를 호출합니다.
    main()
