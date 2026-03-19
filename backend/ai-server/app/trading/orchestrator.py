import copy
import logging
from typing import Any, Dict, Optional
from decimal import Decimal

from app.news.agent import NewsReporterAgent
from app.news.sources import retrieve_news
from app.news.sources_community import retrieve_community_posts

from app.quant.agent import QuantAnalysisAgent
from app.quant.sources import load_json_compressed
from collector.storage import get_storage_dir
import os

from app.shared.agents.judge_agent import JudgeAgent
from app.trading.monitoring import get_current_price
from app.trading.core_api_client import get_trading_account_snapshot, execute_order

logger = logging.getLogger(__name__)


def _extract_holding(account_snapshot: Dict[str, Any], ticker: str) -> Dict[str, Any]:
    current_holding = {
        "quantity": 0,
        "available_quantity": 0,
        "average_price": 0,
        "company_name": ticker,
    }

    for pos in account_snapshot.get("positions", []):
        if str(pos.get("ticker")) != ticker:
            continue

        current_holding = {
            "quantity": int(pos.get("quantity") or 0),
            "available_quantity": int(pos.get("availableQuantity") or 0),
            "average_price": int(float(pos.get("averagePrice") or 0)),
            "company_name": pos.get("companyName") or ticker,
        }
        break

    return current_holding


def _build_hold_order_card(order_card: Dict[str, Any], reason: str, requested_order: Dict[str, Any]) -> Dict[str, Any]:
    adjusted = copy.deepcopy(order_card)
    adjusted["final_stance"] = "hold"
    adjusted["order"] = {
        "action": "hold",
        "order_type": "limit",
        "price": 0,
        "quantity": 0,
        "time_in_force": "day",
    }
    adjusted["adjusted_by_account_state"] = True
    adjusted["adjustment_reason"] = reason
    adjusted["requested_order"] = requested_order
    return adjusted


def apply_account_constraints(
    order_card: Dict[str, Any],
    *,
    available_cash: int,
    current_holding: Dict[str, Any],
    current_price: Decimal,
) -> Dict[str, Any]:
    requested_order = copy.deepcopy(order_card.get("order", {}))
    adjusted = copy.deepcopy(order_card)
    order = adjusted.get("order", {})
    action = str(order.get("action", "hold")).lower()

    if action not in {"buy", "sell"}:
        adjusted["adjusted_by_account_state"] = False
        adjusted["requested_order"] = requested_order
        return adjusted

    effective_price = int(order.get("price") or int(current_price or 0))
    requested_qty = int(order.get("quantity") or 0)

    if effective_price <= 0:
        return _build_hold_order_card(
            adjusted,
            "현재가를 확인할 수 없어 주문을 보류했습니다.",
            requested_order,
        )

    if requested_qty <= 0:
        return _build_hold_order_card(
            adjusted,
            "주문 수량이 0 이하라서 주문을 보류했습니다.",
            requested_order,
        )

    if action == "buy":
        max_qty = available_cash // effective_price if effective_price > 0 else 0
        if max_qty <= 0:
            return _build_hold_order_card(
                adjusted,
                f"주문 가능 금액이 부족해 매수할 수 없습니다. (available_cash={available_cash}, price={effective_price})",
                requested_order,
            )
        adjusted_qty = min(requested_qty, max_qty)
        adjusted["order"]["price"] = effective_price
        adjusted["order"]["quantity"] = adjusted_qty
        adjusted["adjusted_by_account_state"] = adjusted_qty != requested_qty
        adjusted["adjustment_reason"] = (
            f"주문 가능 금액 기준 최대 {max_qty}주까지만 매수 가능해 수량을 조정했습니다."
            if adjusted_qty != requested_qty else
            "주문 가능 금액 범위 내 주문입니다."
        )
        adjusted["requested_order"] = requested_order
        return adjusted

    sellable_quantity = int(current_holding.get("available_quantity") or 0)
    if sellable_quantity <= 0:
        return _build_hold_order_card(
            adjusted,
            "매도 가능한 보유 수량이 없어 주문을 보류했습니다.",
            requested_order,
        )

    adjusted_qty = min(requested_qty, sellable_quantity)
    adjusted["order"]["price"] = effective_price
    adjusted["order"]["quantity"] = adjusted_qty
    adjusted["adjusted_by_account_state"] = adjusted_qty != requested_qty
    adjusted["adjustment_reason"] = (
        f"매도 가능 수량이 {sellable_quantity}주라 주문 수량을 조정했습니다."
        if adjusted_qty != requested_qty else
        "매도 가능 수량 범위 내 주문입니다."
    )
    adjusted["requested_order"] = requested_order
    return adjusted

def run_news_agent(ticker: str, question: str = "이 종목의 향후 단기 주가 방향은 어떨까?") -> Dict[str, Any]:
    """
    RAG(ChromaDB)를 통해 뉴스와 커뮤니티 글을 가져와 NewsReporterAgent에게 넘깁니다.
    """
    logger.info(f"[{ticker}] 1단계: News/Community 데이터 수집 및 NewsAgent 실행")
    
    # 1. 문서 검색 (최근 7일 등 기준)
    news_docs = retrieve_news(ticker, query=question, top_k=5)
    comm_docs = retrieve_community_posts(ticker, query=question, top_k=3)
    
    # 2. 에이전트 호출
    agent = NewsReporterAgent()
    news_card = agent.generate_analysis_card(
        ticker=ticker,
        question=question,
        news_docs=news_docs,
        community_docs=comm_docs
    )
    
    logger.info(f"[{ticker}] News Card 생성 완료 (Stance: {news_card.get('stance')}, Score: {news_card.get('score')})")
    return news_card


def run_quant_agent(ticker: str) -> Dict[str, Any]:
    """
    미리 계산되어 로컬(또는 S3)에 저장된 Quant Feature JSON을 읽어 QuantAnalysisAgent에게 넘깁니다.
    """
    logger.info(f"[{ticker}] 2단계: Quant Data 로드 및 QuantAgent 실행")
    
    # 1. 퀀트 피처 파일 경로 찾기
    features_dir = os.path.join(get_storage_dir(), "features")
    json_path = os.path.join(features_dir, f"{ticker}_features.json")
    
    # 압축된 버전 확인
    if not os.path.exists(json_path):
        json_path = f"{json_path}.gz"
        
    if not os.path.exists(json_path):
        logger.warning(f"[{ticker}] 피처 파일이 없습니다. Fallback 카드 생성.")
        return QuantAnalysisAgent._fallback_card(ticker, "피처 데이터 없음")
        
    # 2. 데이터 로드 및 에이전트 호출
    quant_evidence = load_json_compressed(json_path)
    
    agent = QuantAnalysisAgent()
    quant_card = agent.generate_analysis_card(
        ticker=ticker,
        quant_evidence=quant_evidence
    )
    
    logger.info(f"[{ticker}] Quant Card 생성 완료 (Stance: {quant_card.get('stance')}, Score: {quant_card.get('score')})")
    return quant_card


def run_judge_agent(ticker: str, news_card: Dict[str, Any], quant_card: Dict[str, Any], current_price: Decimal, available_cash: int, current_holding: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    News 카드와 Quant 카드, 그리고 시장 데이터(현재가, 예수금 등)를 종합하여 
    최종 Order Card(매수/매도/보유 등)를 JudgeAgent를 통해 결정합니다.
    """
    logger.info(f"[{ticker}] 3단계: JudgeAgent 최종 주문 결정")
    
    input_payload = {
        "ticker": ticker,
        "current_price": int(current_price),
        "available_cash": available_cash,
        "current_holding": current_holding or {"quantity": 0, "average_price": 0},
        "risk_type": "moderate", # TODO: 나중에 사용자 설정으로 뺄 수 있음
        "news_card": news_card,
        "quant_card": quant_card,
    }
    
    agent = JudgeAgent()
    try:
        order_card = agent.generate_order_card(input_payload)
    except Exception as e:
        logger.error(f"[{ticker}] JudgeAgent 실행 실패: {e}")
        order_card = {"final_stance": "hold", "order": {"action": "hold"}, "error": str(e)}
        
    logger.info(f"[{ticker}] Order Card 생성 완료 (Action: {order_card.get('order', {}).get('action')}, Verdict: {order_card.get('verdict')})")
    return order_card


def orchestrate_trading(
    ticker: str,
    available_cash: int = 5000000,
    user_id: Optional[int] = None,
    account_type: str = "USER",
) -> Dict[str, Any]:
    """전체 에이전트 파이프라인(News -> Quant -> Judge)을 실행합니다."""
    logger.info(f"== [{ticker}] Orchestrator 자동 매매 판단 시작 ==")
    
    # 0단계: 계좌 정보 조회
    account_info = get_trading_account_snapshot(user_id=user_id, account_type=account_type)
    api_available_cash = account_info.get("availableAmt")
    if api_available_cash is not None:
        available_cash = int(api_available_cash)
    current_holding = _extract_holding(account_info, ticker)

    # 1/2단계 병렬 실행 대신 일단 순차 실행 (안정성)
    news_card = run_news_agent(ticker)
    quant_card = run_quant_agent(ticker)
    
    # 실시간 현재가 확인 (Redis)
    curr_price = get_current_price(ticker)
    if not curr_price:
        logger.warning(f"[{ticker}] 실시간 현재가를 가져오지 못해 임시값(0) 적용.")
        curr_price = Decimal("0")
        
    # 3단계
    order_card = run_judge_agent(
        ticker=ticker,
        news_card=news_card,
        quant_card=quant_card,
        current_price=curr_price,
        available_cash=available_cash,
        current_holding=current_holding
    )
    order_card = apply_account_constraints(
        order_card,
        available_cash=available_cash,
        current_holding=current_holding,
        current_price=curr_price,
    )
    order_card["account_snapshot"] = {
        "available_cash": available_cash,
        "holding": current_holding,
        "account_type": account_type,
        "user_id": user_id,
    }
    
    # 4단계: 주문 실행
    order = order_card.get("order", {})
    action = order.get("action", "hold").lower()
    
    if action in ["buy", "sell"]:
        quantity = order.get("quantity", 0)
        price = order.get("price", int(curr_price))
        
        if quantity > 0:
            logger.info(f"[{ticker}] {action.upper()} 주문 실행 요청: {quantity}주 @ {price}원")
            success = execute_order(
                ticker,
                action,
                price,
                quantity,
                user_id=user_id,
                account_type=account_type,
            )
            if success:
                order_card["execution_status"] = "success"
                logger.info(f"[{ticker}] 주문 실행 성공")
            else:
                order_card["execution_status"] = "failed"
                logger.error(f"[{ticker}] 주문 실행 실패")
        else:
            logger.warning(f"[{ticker}] 주문 수량이 0 주이므로 생략합니다.")
            order_card["execution_status"] = "skipped (zero quantity)"
    else:
        logger.info(f"[{ticker}] 판정 결과가 HOLD이므로 주문을 실행하지 않습니다.")
        order_card["execution_status"] = "hold"
        
    logger.info(f"== [{ticker}] Orchestrator 자동 매매 판단 종료 ==")
    return order_card

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    
    # 삼성전자 테스트
    res = orchestrate_trading("005930")
    print("\n최종 주문 카드:", res)
