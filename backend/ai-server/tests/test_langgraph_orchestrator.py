from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.trading.langgraph_orchestrator import get_trading_graph, orchestrate_trading


def setup_function():
    get_trading_graph.cache_clear()


def _analysis_payload():
    return {
        "trade_date": "2026-05-15",
        "news_card": {"stance": "buy", "score": 20, "confidence": 0.8},
        "quant_card": {"stance": "buy", "score": 15, "confidence": 0.7},
        "quant_state": {"risk_context": {"signal_confidence": "high"}},
        "rebuttal_result": {"triggered": False},
    }


@patch("app.trading.langgraph_orchestrator.get_user_profile")
@patch("app.trading.langgraph_orchestrator.get_trading_account_snapshot")
@patch("app.trading.langgraph_orchestrator.get_current_price")
@patch("app.trading.langgraph_orchestrator._load_or_create_ticker_analysis")
@patch("app.trading.langgraph_orchestrator.HistoricalComparisonAgent")
@patch("app.trading.langgraph_orchestrator.JudgeAgent")
@patch("app.trading.langgraph_orchestrator.save_decision_trace")
@patch("app.trading.langgraph_orchestrator.mark_agent_response")
def test_orchestrate_trading_runs_via_langgraph(
    mock_mark_agent_response,
    mock_save_decision_trace,
    mock_judge_class,
    mock_historical_class,
    mock_load_analysis,
    mock_get_price,
    mock_get_account,
    mock_get_profile,
):
    mock_get_profile.return_value = {"investmentStyle": "GROWTH"}
    mock_get_account.return_value = {"availableAmt": 10000000}
    mock_get_price.return_value = Decimal("50000")
    mock_load_analysis.return_value = (_analysis_payload(), "created")
    mock_historical = MagicMock()
    mock_historical_class.return_value = mock_historical
    mock_historical.compare.return_value = {
        "schema": "historical_comparison_v1",
        "similar_cases_count": 3,
        "historical_bias": "bullish",
        "recommendation": "BUY_NORMAL",
        "confidence": 0.7,
        "position_size_multiplier": 1.0,
        "reasons": ["similar cases were constructive"],
        "cases_used": ["trace-old"],
    }
    mock_save_decision_trace.return_value = {
        "decision_trace_id": "trace-1",
        "schema": "agent_decision_trace_v1",
        "path": "storage/decisions/20260515_decisions.jsonl",
        "query_index": {"ticker": "005930"},
    }

    mock_judge = MagicMock()
    mock_judge_class.return_value = mock_judge
    mock_judge.generate_order_card.return_value = {
        "ticker": "005930",
        "final_score": 20,
        "order": {"action": "buy", "order_type": "limit", "quantity": 10, "price": 50000},
        "risk_management": {"stop_loss_price": 48000, "take_profit_price": 55000},
        "verdict": "buy candidate",
    }

    result = orchestrate_trading(ticker="005930", execute_immediately=False)

    assert result["ticker"] == "005930"
    assert result["execution_status"] == "planned"
    assert result["workflow"] == "langgraph"
    assert result["workflow_version"] == "v1"
    assert result["system_error"] is False
    assert result["analysis_cache"]["status"] == "created"
    assert result["historical_comparison"]["recommendation"] == "BUY_NORMAL"
    assert result["risk_review"]["decision"] == "APPROVE"
    assert result["risk_review"]["blocked"] is False
    assert result["decision_trace"]["decision_trace_id"] == "trace-1"
    assert mock_mark_agent_response.call_count == 3
    assert mock_save_decision_trace.call_count == 1
    assert mock_historical.compare.call_count == 1
    judge_payload = mock_judge.generate_order_card.call_args[0][0]
    assert judge_payload["historical_comparison"]["recommendation"] == "BUY_NORMAL"


@patch("app.trading.langgraph_orchestrator.get_user_profile")
@patch("app.trading.langgraph_orchestrator.get_trading_account_snapshot")
@patch("app.trading.langgraph_orchestrator.get_current_price")
@patch("app.trading.langgraph_orchestrator._load_or_create_ticker_analysis")
@patch("app.trading.langgraph_orchestrator.HistoricalComparisonAgent")
@patch("app.trading.langgraph_orchestrator.JudgeAgent")
@patch("app.trading.langgraph_orchestrator.save_decision_trace")
@patch("app.trading.langgraph_orchestrator.mark_agent_response")
def test_orchestrate_trading_marks_system_error_on_analysis_failure(
    mock_mark_agent_response,
    mock_save_decision_trace,
    mock_judge_class,
    mock_historical_class,
    mock_load_analysis,
    mock_get_price,
    mock_get_account,
    mock_get_profile,
):
    mock_get_profile.return_value = {"investmentStyle": "GROWTH"}
    mock_get_account.return_value = {"availableAmt": 10000000}
    mock_get_price.return_value = Decimal("50000")
    mock_load_analysis.side_effect = RuntimeError("analysis unavailable")
    mock_historical = MagicMock()
    mock_historical_class.return_value = mock_historical
    mock_save_decision_trace.return_value = {
        "decision_trace_id": "trace-2",
        "schema": "agent_decision_trace_v1",
        "path": "storage/decisions/20260515_decisions.jsonl",
        "query_index": {"ticker": "005930"},
    }

    mock_judge = MagicMock()
    mock_judge_class.return_value = mock_judge
    mock_judge.generate_order_card.return_value = {
        "ticker": "005930",
        "final_score": 0,
        "order": {"action": "buy", "order_type": "limit", "quantity": 10, "price": 50000},
        "risk_management": {"stop_loss_price": 48000, "take_profit_price": 55000},
        "verdict": "buy candidate",
    }

    result = orchestrate_trading(ticker="005930", execute_immediately=False)

    assert result["system_error"] is True
    assert result["system_error_details"]["news"] == "analysis unavailable"
    assert result["system_error_details"]["quant"] == "analysis unavailable"
    assert result["execution_status"] == "hold"
    assert result["historical_comparison"]["recommendation"] == "INSUFFICIENT_HISTORY"
    assert result["risk_review"]["decision"] == "REJECT"
    assert result["risk_review"]["blocked"] is True
    assert result["risk_blocked_order"]["action"] == "buy"
    assert result["decision_trace"]["decision_trace_id"] == "trace-2"
    assert mock_mark_agent_response.call_count == 1
    assert mock_save_decision_trace.call_count == 1
    assert mock_historical.compare.call_count == 0


@patch("app.trading.langgraph_orchestrator.get_user_profile")
@patch("app.trading.langgraph_orchestrator.get_trading_account_snapshot")
@patch("app.trading.langgraph_orchestrator.get_current_price")
@patch("app.trading.langgraph_orchestrator._load_or_create_ticker_analysis")
@patch("app.trading.langgraph_orchestrator.HistoricalComparisonAgent")
@patch("app.trading.langgraph_orchestrator.JudgeAgent")
@patch("app.trading.langgraph_orchestrator.save_decision_trace")
@patch("app.trading.langgraph_orchestrator.mark_agent_response")
def test_risk_review_blocks_low_confidence_market_buy(
    mock_mark_agent_response,
    mock_save_decision_trace,
    mock_judge_class,
    mock_historical_class,
    mock_load_analysis,
    mock_get_price,
    mock_get_account,
    mock_get_profile,
):
    mock_get_profile.return_value = {"investmentStyle": "GROWTH"}
    mock_get_account.return_value = {"availableAmt": 10000000}
    mock_get_price.return_value = Decimal("50000")
    payload = _analysis_payload()
    payload["quant_state"] = {"risk_context": {"signal_confidence": "low", "entry_risk": "high"}}
    mock_load_analysis.return_value = (payload, "hit")
    mock_historical = MagicMock()
    mock_historical_class.return_value = mock_historical
    mock_historical.compare.return_value = {
        "schema": "historical_comparison_v1",
        "similar_cases_count": 4,
        "historical_bias": "caution",
        "recommendation": "BUY_LESS",
        "confidence": 0.8,
        "position_size_multiplier": 0.5,
        "reasons": ["similar market buys were often blocked"],
        "cases_used": ["trace-old"],
    }
    mock_save_decision_trace.return_value = {
        "decision_trace_id": "trace-3",
        "schema": "agent_decision_trace_v1",
        "path": "storage/decisions/20260515_decisions.jsonl",
        "query_index": {"ticker": "005930"},
    }

    mock_judge = MagicMock()
    mock_judge_class.return_value = mock_judge
    mock_judge.generate_order_card.return_value = {
        "ticker": "005930",
        "final_score": 8,
        "order": {"action": "buy", "order_type": "market", "quantity": 10, "price": 50000},
        "risk_management": {"stop_loss_price": 0, "take_profit_price": 55000},
        "verdict": "risky buy candidate",
    }

    result = orchestrate_trading(ticker="005930", execute_immediately=False)

    assert result["risk_review"]["decision"] == "REJECT"
    assert result["risk_review"]["blocked"] is True
    assert result["historical_comparison"]["recommendation"] == "BUY_LESS"
    assert result["risk_blocked_order"]["quantity"] == 10
    assert result["order"]["action"] == "hold"
    assert result["execution_status"] == "hold"
    assert result["decision_trace"]["decision_trace_id"] == "trace-3"
    assert mock_save_decision_trace.call_count == 1


@patch("app.trading.langgraph_orchestrator.get_user_profile")
@patch("app.trading.langgraph_orchestrator.get_trading_account_snapshot")
@patch("app.trading.langgraph_orchestrator.get_current_price")
@patch("app.trading.langgraph_orchestrator._load_or_create_ticker_analysis")
@patch("app.trading.langgraph_orchestrator.HistoricalComparisonAgent")
@patch("app.trading.langgraph_orchestrator.JudgeAgent")
@patch("app.trading.langgraph_orchestrator.save_decision_trace")
@patch("app.trading.langgraph_orchestrator.mark_agent_response")
def test_historical_multiplier_reduces_buy_quantity(
    mock_mark_agent_response,
    mock_save_decision_trace,
    mock_judge_class,
    mock_historical_class,
    mock_load_analysis,
    mock_get_price,
    mock_get_account,
    mock_get_profile,
):
    mock_get_profile.return_value = {"investmentStyle": "GROWTH"}
    mock_get_account.return_value = {"availableAmt": 10000000}
    mock_get_price.return_value = Decimal("50000")
    mock_load_analysis.return_value = (_analysis_payload(), "hit")
    mock_historical = MagicMock()
    mock_historical_class.return_value = mock_historical
    mock_historical.compare.return_value = {
        "schema": "historical_comparison_v1",
        "similar_cases_count": 5,
        "historical_bias": "caution",
        "recommendation": "BUY_LESS",
        "confidence": 0.8,
        "position_size_multiplier": 0.5,
        "reasons": ["similar cases suggest smaller entry"],
        "cases_used": ["trace-old"],
    }
    mock_save_decision_trace.return_value = {
        "decision_trace_id": "trace-4",
        "schema": "agent_decision_trace_v1",
        "path": "storage/decisions/20260515_decisions.jsonl",
        "query_index": {"ticker": "005930"},
    }

    mock_judge = MagicMock()
    mock_judge_class.return_value = mock_judge
    mock_judge.generate_order_card.return_value = {
        "ticker": "005930",
        "final_score": 20,
        "order": {"action": "buy", "order_type": "limit", "quantity": 10, "price": 50000},
        "risk_management": {"stop_loss_price": 48000, "take_profit_price": 55000},
        "verdict": "buy candidate",
    }

    result = orchestrate_trading(ticker="005930", execute_immediately=False)

    assert result["historical_comparison"]["recommendation"] == "BUY_LESS"
    assert result["risk_review"]["decision"] == "REDUCE_SIZE"
    assert result["risk_review"]["approved_quantity"] == 5
    assert result["order"]["quantity"] == 5
    assert result["execution_status"] == "planned"
