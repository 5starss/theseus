import copy
import logging
from decimal import Decimal
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _position_sizing_policy(user_investment_style: str) -> tuple[float, float]:
    style = str(user_investment_style or "GROWTH").upper()
    if style == "BALANCED":
        return 0.15, 0.20
    if style == "AGGRESSIVE":
        return 0.40, 0.50
    return 0.25, 0.35


def _confidence_multiplier(signal_confidence: Any) -> float:
    if isinstance(signal_confidence, str):
        normalized = signal_confidence.strip().lower()
        if normalized == "high":
            return 1.0
        if normalized == "medium":
            return 0.75
        if normalized == "low":
            return 0.5
    try:
        confidence_value = float(signal_confidence)
    except Exception:
        return 0.75
    if confidence_value < 0.5:
        return 0.5
    if confidence_value < 0.75:
        return 0.75
    return 1.0


def cap_buy_quantity(
    *,
    requested_qty: int,
    available_cash: int,
    current_holding: Dict[str, Any],
    effective_price: int,
    user_investment_style: str = "GROWTH",
    signal_confidence: Any = None,
) -> tuple[int, Dict[str, Any]]:
    order_ratio, position_ratio = _position_sizing_policy(user_investment_style)
    confidence_ratio = _confidence_multiplier(signal_confidence)
    current_quantity = int(current_holding.get("quantity") or 0)
    total_asset_value = available_cash + current_quantity * effective_price
    current_position_value = current_quantity * effective_price
    order_budget = int(available_cash * order_ratio * confidence_ratio)
    position_budget = max(0, int(total_asset_value * position_ratio) - current_position_value)
    max_qty_by_cash = available_cash // effective_price if effective_price > 0 else 0
    max_qty_by_order_budget = order_budget // effective_price if effective_price > 0 else 0
    max_qty_by_position_budget = position_budget // effective_price if effective_price > 0 else 0
    max_qty = min(max_qty_by_cash, max_qty_by_order_budget, max_qty_by_position_budget)
    capped_qty = min(max(0, requested_qty), max(0, max_qty))
    return capped_qty, {
        "order_ratio": order_ratio,
        "position_ratio": position_ratio,
        "confidence_ratio": confidence_ratio,
        "order_budget": order_budget,
        "position_budget": position_budget,
        "max_qty_by_cash": max_qty_by_cash,
        "max_qty_by_order_budget": max_qty_by_order_budget,
        "max_qty_by_position_budget": max_qty_by_position_budget,
        "max_qty": max_qty,
    }


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
    user_investment_style: str = "GROWTH",
    signal_confidence: Any = None,
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
        adjusted_qty, sizing = cap_buy_quantity(
            requested_qty=requested_qty,
            available_cash=available_cash,
            current_holding=current_holding,
            effective_price=effective_price,
            user_investment_style=user_investment_style,
            signal_confidence=signal_confidence,
        )
        max_qty = sizing["max_qty"]
        if max_qty <= 0:
            return _build_hold_order_card(
                adjusted,
                (
                    "투자 성향/신호 확신도 기준 주문 가능 한도가 부족해 매수할 수 없습니다. "
                    f"(available_cash={available_cash}, price={effective_price}, "
                    f"order_ratio={sizing['order_ratio']}, position_ratio={sizing['position_ratio']}, confidence_ratio={sizing['confidence_ratio']})"
                ),
                requested_order,
            )
        adjusted["order"]["price"] = effective_price
        adjusted["order"]["quantity"] = adjusted_qty
        adjusted["adjusted_by_account_state"] = adjusted_qty != requested_qty
        adjusted["adjustment_reason"] = (
            (
                f"투자 성향({user_investment_style})과 신호 확신도 기준으로 최대 {max_qty}주까지만 매수 가능해 수량을 조정했습니다. "
                f"(1회 주문 한도={sizing['order_budget']:,}원, 종목 잔여 한도={sizing['position_budget']:,}원)"
            )
            if adjusted_qty != requested_qty else
            "투자 성향 및 신호 확신도 한도 범위 내 주문입니다."
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
