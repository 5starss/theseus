import pandas as pd

from app.quant.feature_engineer import IntradayFeatureEngineer
from app.quant.pipeline import generate_quant_signal


def _make_intraday_df(days: int = 25) -> pd.DataFrame:
    rows = []
    base_price = 70000.0
    session_dates = pd.date_range("2024-01-02", periods=days, freq="B")
    idx = 0
    for day in session_dates:
        start = day.replace(hour=9, minute=0, second=0)
        for minute in range(390):
            ts = start + pd.Timedelta(minutes=minute)
            price = base_price + idx * 2.0 + (minute % 11) * 0.3
            rows.append(
                {
                    "ts": ts,
                    "open": price - 0.4,
                    "high": price + 0.8,
                    "low": price - 0.9,
                    "close": price,
                    "volume": 1000 + (idx % 50) * 10,
                }
            )
            idx += 1
    return pd.DataFrame(rows)


def test_intraday_feature_engineer_mtf_generates_columns():
    raw_df = _make_intraday_df()
    feat_df = IntradayFeatureEngineer(horizon_minutes=5, feature_profile="mtf").build(raw_df)

    assert not feat_df.empty
    assert "mtf_5m_rsi_14" in feat_df.columns
    assert "mtf_15m_trend" in feat_df.columns
    assert "mtf_60m_dist_sma_20" in feat_df.columns
    assert "mtf_1d_rsi_14" in feat_df.columns


def test_generate_quant_signal_returns_filtered_mtf_payload(monkeypatch):
    raw_df = _make_intraday_df(days=40)

    monkeypatch.setattr("app.quant.pipeline.resolve_raw_path", lambda **kwargs: "/tmp/raw.json.gz")
    monkeypatch.setattr("app.quant.pipeline.quant_load_raw_from_storage", lambda path: raw_df)

    def _fake_generate(self, ticker, quant_evidence):
        assert ticker == "005930"
        assert any(key.startswith("mtf_") for key in quant_evidence)
        assert "target_return" not in quant_evidence
        return {
            "$schema": "analysis_card_v1",
            "agent": "quant",
            "ticker": ticker,
            "timestamp": "2026-01-01T00:00:00+09:00",
            "stance": "hold",
            "confidence": 0.5,
            "score": 0,
            "signal_breakdown": {},
            "top_reasons": ["테스트"],
            "risk_flags": [],
            "requested_action": {"preference": "hold", "avoid_if": "none"},
        }

    monkeypatch.setattr("app.quant.pipeline.QuantAnalysisAgent.generate_analysis_card", _fake_generate)

    result = generate_quant_signal(ticker="005930", data_dir="/tmp", run_fetch=False, horizon_minutes=5)

    assert result["status"] == "ok"
    assert result["analysis_card"]["ticker"] == "005930"
    assert result["raw_result"]["mode"] == "mtf_llm_mvp"
    assert result["raw_result"]["feature_rows"] > 0
    assert any(key.startswith("mtf_") for key in result["quant_evidence"])
