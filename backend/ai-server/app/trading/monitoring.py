import logging
from typing import Dict, Any
from decimal import Decimal
from datetime import datetime

from app.shared.infra.redis_client import redis_client
from app.trading.core_api_client import execute_order
from app.trading.constants import KST
from app.trading.market_data import get_current_price
from app.trading.strategy_store import (
    load_strategy_payload,
    resolve_strategy_s3_key,
    save_strategy_payload,
    strategy_index_key_for_today,
    write_json,
)
from app.shared.infra.s3_client import s3_client

logger = logging.getLogger(__name__)


def _exit_rule_policy(user_investment_style: str) -> tuple[float, float]:
    style = str(user_investment_style or "GROWTH").upper()
    if style == "BALANCED":
        return 0.05, 0.10
    if style == "AGGRESSIVE":
        return 0.20, 0.30
    return 0.10, 0.15


def _build_exit_plan(judge_decision: Dict[str, Any], executed_price: int, executed_quantity: int) -> Dict[str, Any] | None:
    order = judge_decision.get("order", {})
    entry_action = str(order.get("action", "hold")).lower()
    if entry_action not in {"buy", "sell"} or executed_price <= 0 or executed_quantity <= 0:
        return None

    account_snapshot = judge_decision.get("account_snapshot", {})
    user_style = str(account_snapshot.get("user_investment_style") or "GROWTH").upper()
    stop_loss_ratio, take_profit_ratio = _exit_rule_policy(user_style)
    position_side = "long" if entry_action == "buy" else "short"
    exit_action = "sell" if position_side == "long" else "buy"

    if position_side == "long":
        stop_loss_price = int(round(executed_price * (1 - stop_loss_ratio)))
        take_profit_price = int(round(executed_price * (1 + take_profit_ratio)))
    else:
        stop_loss_price = int(round(executed_price * (1 + stop_loss_ratio)))
        take_profit_price = int(round(executed_price * (1 - take_profit_ratio)))

    return {
        "active": True,
        "position_side": position_side,
        "entry_action": entry_action,
        "exit_action": exit_action,
        "entry_price": executed_price,
        "entry_quantity": executed_quantity,
        "remaining_quantity": executed_quantity,
        "stop_loss_ratio": stop_loss_ratio,
        "take_profit_ratio": take_profit_ratio,
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
        "take_profit_quantity": executed_quantity,
        "stop_loss_quantity": executed_quantity,
        "status": "armed",
        "triggered_by": None,
    }


def _should_trigger_exit(position_side: str, current_price: Decimal, stop_loss_price: int, take_profit_price: int) -> str | None:
    if position_side == "long":
        if current_price <= Decimal(stop_loss_price):
            return "stop_loss"
        if current_price >= Decimal(take_profit_price):
            return "take_profit"
        return None
    if current_price >= Decimal(stop_loss_price):
        return "stop_loss"
    if current_price <= Decimal(take_profit_price):
        return "take_profit"
    return None

def monitor_tickers(tickers: Dict[str, Dict[str, Decimal]]):
    """
    지정된 종목들의 시세를 모니터링합니다.
    tickers: { 'ticker': { 'target_buy': 204000, 'stop_loss': 199000, 'take_profit': 215000 } }
    
    현재는 시세 조회 기능 위주로 구현되어 있으며, 
    추후 주문 로직(Orchestrator 연동)이 추가될 예정입니다.
    """
    logger.debug(f"실시간 모니터링 시작: {list(tickers.keys())}")
    
    for ticker, strategy in tickers.items():
        current_price = get_current_price(ticker)
        if current_price:
            logger.debug(f"[{ticker}] 현재가: {current_price:,} | 전략: {strategy}")
            
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
        if monitor_status in {"skipped", "failed"}:
            continue

        ticker = str(decision.get("ticker") or judge_decision.get("ticker") or "")
        current_price = get_current_price(ticker) if ticker else None

        if monitor_status == "executed":
            exit_plan = decision.get("exit_plan")
            if not isinstance(exit_plan, dict) or not exit_plan.get("active"):
                continue
            if current_price is None:
                processed.append({"ticker": ticker, "status": "waiting_price"})
                continue

            trigger_reason = _should_trigger_exit(
                str(exit_plan.get("position_side") or "long"),
                current_price,
                int(exit_plan.get("stop_loss_price") or 0),
                int(exit_plan.get("take_profit_price") or 0),
            )
            if not trigger_reason:
                processed.append(
                    {
                        "ticker": ticker,
                        "status": "holding",
                        "current_price": int(current_price),
                        "stop_loss_price": exit_plan.get("stop_loss_price"),
                        "take_profit_price": exit_plan.get("take_profit_price"),
                    }
                )
                continue

            account_snapshot = judge_decision.get("account_snapshot", {})
            exit_quantity = int(exit_plan.get(f"{trigger_reason}_quantity") or exit_plan.get("remaining_quantity") or 0)
            if exit_quantity <= 0:
                exit_plan["active"] = False
                exit_plan["status"] = "completed"
                changed = True
                continue

            success = execute_order(
                ticker=ticker,
                order_type=str(exit_plan.get("exit_action") or "sell"),
                price=int(current_price),
                quantity=exit_quantity,
                user_id=account_snapshot.get("user_id"),
                account_type=account_snapshot.get("account_type", "AI"),
            )
            changed = True
            exit_plan["checked_at"] = datetime.now(KST).isoformat()
            exit_plan["triggered_by"] = trigger_reason
            exit_plan["trigger_price"] = int(current_price)
            if success:
                exit_plan["remaining_quantity"] = max(0, int(exit_plan.get("remaining_quantity") or 0) - exit_quantity)
                exit_plan["active"] = exit_plan["remaining_quantity"] > 0
                exit_plan["status"] = "completed" if not exit_plan["active"] else "partial_exit"
                decision["monitor_note"] = f"룰베이스 {trigger_reason} 조건 충족으로 청산 주문을 실행했습니다."
                processed.append({"ticker": ticker, "status": f"exit_{trigger_reason}", "price": int(current_price)})
            else:
                exit_plan["status"] = "exit_failed"
                processed.append({"ticker": ticker, "status": "exit_failed", "price": int(current_price)})
            continue

        order = judge_decision.get("order", {})
        action = str(order.get("action", "hold")).lower()
        quantity = int(order.get("quantity", 0) or 0)
        target_price = int(order.get("price", 0) or 0)

        if action not in {"buy", "sell"} or quantity <= 0 or target_price <= 0 or not ticker:
            decision["monitor_status"] = "skipped"
            decision["monitor_note"] = "주문 조건이 유효하지 않아 모니터링 대상에서 제외했습니다."
            changed = True
            continue

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
            decision["exit_plan"] = _build_exit_plan(judge_decision, int(current_price), quantity)
            processed.append({"ticker": ticker, "status": "executed", "price": int(current_price)})
        else:
            decision["monitor_status"] = "failed"
            decision["monitor_note"] = "조건 충족 후 주문 실행에 실패했습니다."
            judge_decision["execution_status"] = "failed"
            processed.append({"ticker": ticker, "status": "failed", "price": int(current_price)})

    if changed:
        archive = payload.setdefault("archive", {})
        archive["s3_uploaded"] = False
        archive["s3_sync_pending"] = True
        save_strategy_payload(redis_key, payload)
        local_path = payload.get("archive", {}).get("local_path")
        if local_path:
            write_json(local_path, payload)

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


def sync_pending_strategy_archives() -> Dict[str, Any]:
    strategy_keys = sorted(redis_client.get_client().smembers(strategy_index_key_for_today()))
    if not strategy_keys:
        return {"status": "ok", "message": "no_strategy_files", "synced_count": 0}

    synced_count = 0
    failed = []

    for redis_key in strategy_keys:
        try:
            payload = load_strategy_payload(redis_key)
        except FileNotFoundError:
            continue

        archive = payload.get("archive", {})
        if not archive.get("s3_sync_pending"):
            continue

        local_path = archive.get("local_path")
        if not local_path:
            failed.append({"redis_key": redis_key, "reason": "missing_local_path"})
            continue

        uploaded = s3_client.upload_file(local_path, resolve_strategy_s3_key(payload))
        if not uploaded:
            failed.append({"redis_key": redis_key, "reason": "upload_failed"})
            continue

        archive["s3_uploaded"] = True
        archive["s3_sync_pending"] = False
        save_strategy_payload(redis_key, payload)
        write_json(local_path, payload)
        synced_count += 1

    return {
        "status": "ok",
        "synced_count": synced_count,
        "failure_count": len(failed),
        "failures": failed,
    }

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
