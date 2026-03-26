from decimal import Decimal

from app.trading.account_service import apply_account_constraints, cap_buy_quantity


def test_cap_buy_quantity_blocks_additional_buy_when_position_ratio_is_full():
    capped_qty, sizing = cap_buy_quantity(
        requested_qty=300,
        available_cash=64000900,
        current_holding={"quantity": 620},
        effective_price=191600,
        user_investment_style="AGGRESSIVE",
        signal_confidence="medium",
    )

    assert capped_qty == 0
    assert sizing["max_qty_by_cash"] > 0
    assert sizing["max_qty_by_position_budget"] == 0


def test_apply_account_constraints_forces_hold_when_position_ratio_blocks_additional_buy():
    order_card = {
        "ticker": "005930",
        "final_stance": "buy",
        "verdict": "추가 매수가 타당하다.",
        "order": {
            "action": "buy",
            "order_type": "market",
            "price": 0,
            "quantity": 300,
            "time_in_force": "day",
        },
    }

    adjusted = apply_account_constraints(
        order_card,
        available_cash=64000900,
        current_holding={"quantity": 620, "available_quantity": 620, "average_price": 102920},
        current_price=Decimal("191600"),
        user_investment_style="AGGRESSIVE",
        signal_confidence="medium",
    )

    assert adjusted["order"]["action"] == "hold"
    assert adjusted["order"]["quantity"] == 0
    assert adjusted["adjusted_by_account_state"] is True
    assert adjusted["verdict"].startswith("계좌 상태 또는 주문 제약으로 이번 주문은 보류합니다.")


def test_apply_account_constraints_updates_verdict_when_forced_to_hold():
    order_card = {
        "ticker": "005930",
        "final_stance": "buy",
        "verdict": "추가 매수가 타당하다.",
        "order": {
            "action": "buy",
            "order_type": "market",
            "price": 0,
            "quantity": 1,
            "time_in_force": "day",
        },
    }

    adjusted = apply_account_constraints(
        order_card,
        available_cash=1000,
        current_holding={"quantity": 0, "available_quantity": 0, "average_price": 0},
        current_price=Decimal("191600"),
        user_investment_style="AGGRESSIVE",
        signal_confidence="medium",
    )

    assert adjusted["order"]["action"] == "hold"
    assert adjusted["final_stance"] == "hold"
    assert adjusted["verdict"].startswith("계좌 상태 또는 주문 제약으로 이번 주문은 보류합니다.")
