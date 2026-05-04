from decimal import Decimal
from unittest.mock import MagicMock, patch

from app.trading.langgraph_orchestrator import orchestrate_trading


@patch("app.trading.langgraph_orchestrator.get_user_profile")
@patch("app.trading.langgraph_orchestrator.get_trading_account_snapshot")
@patch("app.trading.langgraph_orchestrator.get_current_price")
@patch("app.trading.langgraph_orchestrator.run_news_agent")
@patch("app.trading.langgraph_orchestrator.run_quant_agent")
@patch("app.trading.langgraph_orchestrator.run_rebuttal_agent")
@patch("app.trading.langgraph_orchestrator.JudgeAgent")
@patch("app.trading.langgraph_orchestrator.mark_agent_response")
def test_orchestrate_trading_runs_via_langgraph(
    mock_mark_agent_response,
    mock_judge_class,
    mock_run_rebuttal,
    mock_run_quant,
    mock_run_news,
    mock_get_price,
    mock_get_account,
    mock_get_profile,
):
    mock_get_profile.return_value = {"investmentStyle": "GROWTH"}
    mock_get_account.return_value = {"availableAmt": 10000000}
    mock_get_price.return_value = Decimal("50000")
    mock_run_news.return_value = {"stance": "buy", "score": 20, "confidence": 0.8}
    mock_run_quant.return_value = (
        {"stance": "buy", "score": 15, "confidence": 0.7},
        {"risk_context": {"signal_confidence": "high"}},
    )
    mock_run_rebuttal.return_value = {"triggered": False}

    mock_judge = MagicMock()
    mock_judge_class.return_value = mock_judge
    mock_judge.generate_order_card.return_value = {
        "ticker": "005930",
        "order": {"action": "buy", "quantity": 10, "price": 50000},
        "verdict": "테스트 판정",
    }

    result = orchestrate_trading(ticker="005930", execute_immediately=False)

    assert result["ticker"] == "005930"
    assert result["execution_status"] == "planned"
    assert result["workflow"] == "langgraph"
    assert result["workflow_version"] == "v1"
    assert result["system_error"] is False
    assert mock_mark_agent_response.call_count == 3


@patch("app.trading.langgraph_orchestrator.get_user_profile")
@patch("app.trading.langgraph_orchestrator.get_trading_account_snapshot")
@patch("app.trading.langgraph_orchestrator.get_current_price")
@patch("app.trading.langgraph_orchestrator.run_news_agent")
@patch("app.trading.langgraph_orchestrator.run_quant_agent")
@patch("app.trading.langgraph_orchestrator.run_rebuttal_agent")
@patch("app.trading.langgraph_orchestrator.JudgeAgent")
@patch("app.trading.langgraph_orchestrator.mark_agent_response")
def test_orchestrate_trading_marks_system_error_on_agent_failure(
    mock_mark_agent_response,
    mock_judge_class,
    mock_run_rebuttal,
    mock_run_quant,
    mock_run_news,
    mock_get_price,
    mock_get_account,
    mock_get_profile,
):
    mock_get_profile.return_value = {"investmentStyle": "GROWTH"}
    mock_get_account.return_value = {"availableAmt": 10000000}
    mock_get_price.return_value = Decimal("50000")
    mock_run_news.side_effect = RuntimeError("news unavailable")
    mock_run_quant.return_value = (
        {"stance": "buy", "score": 15, "confidence": 0.7},
        {"risk_context": {"signal_confidence": "high"}},
    )
    mock_run_rebuttal.return_value = {"triggered": False}

    mock_judge = MagicMock()
    mock_judge_class.return_value = mock_judge
    mock_judge.generate_order_card.return_value = {
        "ticker": "005930",
        "order": {"action": "hold", "quantity": 0, "price": 0},
        "verdict": "보수적 관망",
    }

    result = orchestrate_trading(ticker="005930", execute_immediately=False)

    assert result["system_error"] is True
    assert result["system_error_details"]["news"] == "news unavailable"
    assert result["execution_status"] == "hold"
    assert mock_mark_agent_response.call_count == 2
