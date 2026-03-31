from datetime import date

import pandas as pd

from runner.simulate_agent_replay import SimulationAccount, _resolve_signal_confidence, simulate_fill


def test_resolve_signal_confidence_prefers_quant_state_value():
    signal_confidence = _resolve_signal_confidence(
        news_card={"confidence": 0.2},
        quant_card={"confidence": 0.4},
        quant_state={"risk_context": {"signal_confidence": "high"}},
    )

    assert signal_confidence == "high"


def test_resolve_signal_confidence_falls_back_to_average_card_confidence():
    signal_confidence = _resolve_signal_confidence(
        news_card={"confidence": 0.2},
        quant_card={"confidence": 0.4},
        quant_state={},
    )

    assert signal_confidence == 0.3


def test_simulate_fill_executes_market_buy_with_zero_price():
    intraday_df = pd.DataFrame(
        [
            {"ts": "2026-03-24T09:00:00", "close": 1000},
            {"ts": "2026-03-24T09:01:00", "close": 1010},
        ]
    )
    account = SimulationAccount(cash=5000)

    fill = simulate_fill(
        ticker="005930",
        trade_date=date(2026, 3, 24),
        intraday_df=intraday_df,
        order_card={
            "order": {
                "action": "buy",
                "order_type": "market",
                "price": 0,
                "quantity": 3,
            }
        },
        account=account,
    )

    assert fill["status"] == "filled"
    assert fill["executed_price"] == 1000
    assert fill["executed_quantity"] == 3
    assert account.cash == 2000


def test_simulate_fill_keeps_limit_order_logic():
    intraday_df = pd.DataFrame(
        [
            {"ts": "2026-03-24T09:00:00", "close": 1100},
            {"ts": "2026-03-24T09:01:00", "close": 1000},
        ]
    )
    account = SimulationAccount(cash=5000)

    fill = simulate_fill(
        ticker="005930",
        trade_date=date(2026, 3, 24),
        intraday_df=intraday_df,
        order_card={
            "order": {
                "action": "buy",
                "order_type": "limit",
                "price": 1000,
                "quantity": 2,
            }
        },
        account=account,
    )

    assert fill["status"] == "filled"
    assert fill["executed_price"] == 1000
    assert fill["executed_quantity"] == 2
