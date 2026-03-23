import copy
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def extract_holding_from_snapshot(account_snapshot: Dict[str, Any], ticker: str) -> Dict[str, Any]:
    """
    Account Snapshot에서 특정 종목의 보유 정보를 추출합니다.
    """
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


def apply_account_constraints(
    order_card: Dict[str, Any],
    *,
    available_cash: int,
    current_holding: Dict[str, Any],
    current_price: Decimal,
) -> Dict[str, Any]:
    """
    사용자의 실제 가용 현금 및 보유 수량을 바탕으로 주문 수량을 조정하거나 보류합니다.
    """
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

    # Sell logic
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


def build_account_summary(
    *,
    available_cash: int,
    current_holding: Dict[str, Any],
    account_type: str,
    user_id: Optional[int],
    strategy_profile: Dict[str, str],
    strategy_slot: str,
) -> Dict[str, Any]:
    """
    최종 결과 리포트에 포함할 계좌 스냅샷 정보를 생성합니다.
    """
    from app.trading.strategy_service import build_signal_weights
    
    return {
        "available_cash": available_cash,
        "holding": current_holding,
        "account_type": account_type,
        "user_id": user_id,
        "invest_style": strategy_profile["invest_style"],
        "user_investment_style": strategy_profile["user_investment_style"],
        "risk_type": strategy_profile["risk_type"],
        "strategy_slot": strategy_slot,
        "signal_weights": build_signal_weights(strategy_slot),
    }


def _build_hold_order_card(order_card: Dict[str, Any], reason: str, requested_order: Dict[str, Any]) -> Dict[str, Any]:
    """내부 보조 함수: 주문을 HOLD로 강제 변환"""
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
