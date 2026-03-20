import logging
from typing import Dict, Any
from decimal import Decimal

from app.shared.infra.redis_client import redis_client
from app.shared.infra.s3_client import s3_client
from app.trading.core_api_client import execute_order
from app.trading.constants import KST
from app.trading.market_data import get_current_price
from app.trading.strategy_store import (
    load_strategy_payload,
    resolve_strategy_s3_key,
    save_strategy_payload,
    strategy_index_key_for_today,
)

logger = logging.getLogger(__name__)

def monitor_tickers(tickers: Dict[str, Dict[str, Decimal]]):
    """
    지정된 종목들의 시세를 모니터링합니다.
    tickers: { 'ticker': { 'target_buy': 204000, 'stop_loss': 199000, 'take_profit': 215000 } }
    
    현재는 시세 조회 기능 위주로 구현되어 있으며, 
    추후 주문 로직(Orchestrator 연동)이 추가될 예정입니다.
    """
    logger.info(f"실시간 모니터링 시작: {list(tickers.keys())}")
    
    for ticker, strategy in tickers.items():
        current_price = get_current_price(ticker)
        if current_price:
            logger.info(f"[{ticker}] 현재가: {current_price:,} | 전략: {strategy}")
            
            # TODO: 전략 매칭 및 주문 로직 구현 (Phase 4 후반부)
        else:
            logger.warning(f"[{ticker}] 시세 데이터를 가져올 수 없습니다.")


def _should_execute_order(action: str, current_price: Decimal, target_price: int) -> bool:
    if action == "buy":
        return current_price <= Decimal(target_price)
    if action == "sell":
        return current_price >= Decimal(target_price)
    return False


def process_saved_strategy(redis_key: str) -> Dict[str, Any]:
    payload = load_strategy_payload(redis_key)
    changed = False
    processed = []

    for decision in payload.get("decisions", []):
        if "judge_decision" not in decision:
            continue

        judge_decision = decision["judge_decision"]
        monitor_status = decision.get("monitor_status", "pending")
        if monitor_status in {"executed", "skipped", "failed"}:
            continue

        order = judge_decision.get("order", {})
        action = str(order.get("action", "hold")).lower()
        quantity = int(order.get("quantity", 0) or 0)
        target_price = int(order.get("price", 0) or 0)
        ticker = str(decision.get("ticker") or judge_decision.get("ticker") or "")

        if action not in {"buy", "sell"} or quantity <= 0 or target_price <= 0 or not ticker:
            decision["monitor_status"] = "skipped"
            decision["monitor_note"] = "주문 조건이 유효하지 않아 모니터링 대상에서 제외했습니다."
            changed = True
            continue

        current_price = get_current_price(ticker)
        if current_price is None:
            processed.append({"ticker": ticker, "status": "waiting_price"})
            continue

        if not _should_execute_order(action, current_price, target_price):
            processed.append(
                {
                    "ticker": ticker,
                    "status": "waiting_trigger",
                    "current_price": int(current_price),
                    "target_price": target_price,
                }
            )
            continue

        account_snapshot = judge_decision.get("account_snapshot", {})
        success = execute_order(
            ticker=ticker,
            order_type=action,
            price=target_price,
            quantity=quantity,
            user_id=account_snapshot.get("user_id"),
            account_type=account_snapshot.get("account_type", "AI"),
        )
        changed = True
        decision["monitor_checked_at"] = datetime.now(KST).isoformat()
        decision["trigger_price"] = int(current_price)
        if success:
            decision["monitor_status"] = "executed"
            decision["monitor_note"] = "저장된 전략과 현재가 조건이 일치해 주문을 실행했습니다."
            judge_decision["execution_status"] = "success"
            processed.append({"ticker": ticker, "status": "executed", "price": int(current_price)})
        else:
            decision["monitor_status"] = "failed"
            decision["monitor_note"] = "조건 충족 후 주문 실행에 실패했습니다."
            judge_decision["execution_status"] = "failed"
            processed.append({"ticker": ticker, "status": "failed", "price": int(current_price)})

    if changed:
        save_strategy_payload(redis_key, payload)
        local_path = payload.get("archive", {}).get("local_path")
        if local_path:
            s3_client.upload_file(local_path, resolve_strategy_s3_key(payload))

    return {
        "redis_key": redis_key,
        "changed": changed,
        "processed": processed,
    }


def process_saved_strategies() -> Dict[str, Any]:
    strategy_keys = sorted(redis_client.get_client().smembers(strategy_index_key_for_today()))
    if not strategy_keys:
        return {"status": "ok", "message": "no_strategy_files", "file_count": 0}

    results = [process_saved_strategy(redis_key) for redis_key in strategy_keys]
    return {"status": "ok", "file_count": len(strategy_keys), "results": results}

if __name__ == "__main__":
    # 테스트용 코드 (로컬 실행 시)
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    logging.basicConfig(level=logging.INFO)
    
    # 예시 종목 (삼성전자 등)
    test_tickers = {
        "005930": {"target_buy": Decimal("71000"), "stop_loss": Decimal("69000"), "take_profit": Decimal("75000")}
    }
    
    monitor_tickers(test_tickers)
