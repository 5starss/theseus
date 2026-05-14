import os
import sys
import time
import threading
from decimal import Decimal
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.append(os.path.abspath("."))

from app.trading.langgraph_orchestrator import orchestrate_trading
from app.trading.analysis_store import _get_db_conn, ANALYSIS_WORKFLOW_VERSION, current_trade_date

def cleanup_cache(ticker):
    try:
        with _get_db_conn() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM ticker_analysis_cache WHERE ticker = %s", (ticker,))
        print(f"Cleaned up cache for {ticker}")
    except Exception as e:
        print(f"Cleanup failed: {e}")

def mock_news_agent(ticker, question=None):
    print(f"[MOCK] Running NewsAgent for {ticker}...")
    time.sleep(2)
    return {
        "score": 70,
        "confidence": 0.8,
        "stance": "buy",
        "top_reasons": ["Good news mock"],
        "risk_flags": []
    }

def mock_quant_agent(ticker):
    print(f"[MOCK] Running QuantAgent for {ticker}...")
    time.sleep(2)
    return {
        "score": 60,
        "confidence": 0.7,
        "stance": "buy",
        "top_reasons": ["Good quant mock"],
        "risk_flags": []
    }, {"dummy": "state"}

def mock_rebuttal_agent(ticker, news, quant, **kwargs):
    print(f"[MOCK] Running RebuttalAgent for {ticker}...")
    return {"triggered": False, "rebuttal_round": 0}

# Mocks for other dependencies in orchestrator
# patch.multiple needs attribute names relative to the target module
MOCKS_ATTRS = {
    "get_user_profile": MagicMock(return_value={"investmentStyle": "GROWTH"}),
    "get_trading_account_snapshot": MagicMock(return_value={"availableAmt": 10000000, "positions": []}),
    "get_current_price": MagicMock(return_value=Decimal("50000")),
    "mark_agent_response": MagicMock(),
    "execute_order": MagicMock(return_value=True),
}

def test_sequential_caching():
    ticker = "TEST_SEQ_001"
    cleanup_cache(ticker)
    
    with patch("app.trading.langgraph_orchestrator.run_news_agent", side_effect=mock_news_agent), \
         patch("app.trading.langgraph_orchestrator.run_quant_agent", side_effect=mock_quant_agent), \
         patch("app.trading.langgraph_orchestrator.run_rebuttal_agent", side_effect=mock_rebuttal_agent), \
         patch("app.trading.analysis_store.s3_client.upload_file", return_value=True), \
         patch("app.trading.analysis_store.s3_client.download_file", return_value=True):
        
        with patch.multiple("app.trading.langgraph_orchestrator", **MOCKS_ATTRS):
            print("\n--- First Call (should create) ---")
            result1 = orchestrate_trading(ticker=ticker, strategy_slot="1200")
            cache_info1 = result1.get("analysis_cache", {})
            print(f"Result 1 Status: {cache_info1.get('status')}")
            
            print("\n--- Second Call (should hit cache) ---")
            result2 = orchestrate_trading(ticker=ticker, strategy_slot="1200")
            cache_info2 = result2.get("analysis_cache", {})
            print(f"Result 2 Status: {cache_info2.get('status')}")
            
            if cache_info1.get("status") != "created":
                raise Exception(f"Expected 'created', got {cache_info1.get('status')}")
            if cache_info2.get("status") != "hit":
                raise Exception(f"Expected 'hit', got {cache_info2.get('status')}")
            print("\nSequential Caching Test Passed!")

def test_concurrent_caching():
    ticker = "TEST_CONC_002"
    cleanup_cache(ticker)
    
    results = []
    
    def run_trading(thread_id):
        print(f"Thread {thread_id} starting...")
        with patch("app.trading.langgraph_orchestrator.run_news_agent", side_effect=mock_news_agent), \
             patch("app.trading.langgraph_orchestrator.run_quant_agent", side_effect=mock_quant_agent), \
             patch("app.trading.langgraph_orchestrator.run_rebuttal_agent", side_effect=mock_rebuttal_agent), \
             patch("app.trading.analysis_store.s3_client.upload_file", return_value=True), \
             patch("app.trading.analysis_store.s3_client.download_file", return_value=True), \
             patch.multiple("app.trading.langgraph_orchestrator", **MOCKS_ATTRS):
            try:
                res = orchestrate_trading(ticker=ticker, strategy_slot="1200")
                results.append(res)
            except Exception as e:
                print(f"Thread {thread_id} error: {e}")
        print(f"Thread {thread_id} finished.")

    t1 = threading.Thread(target=run_trading, args=(1,))
    t2 = threading.Thread(target=run_trading, args=(2,))
    
    t1.start()
    time.sleep(1.0) # Ensure t1 starts first and acquires "running"
    t2.start()
    
    t1.join()
    t2.join()
    
    statuses = [r.get("analysis_cache", {}).get("status") for r in results]
    print(f"\nConcurrent Statuses: {statuses}")
    
    # One should be 'created', the other 'wait_hit'
    if "created" not in statuses:
        raise Exception("Expected 'created' in statuses")
    if "wait_hit" not in statuses:
        raise Exception("Expected 'wait_hit' in statuses")
    print("\nConcurrent Caching Test Passed!")

if __name__ == "__main__":
    # Ensure tables are created
    from app.trading.analysis_store import _ensure_table
    try:
        _ensure_table()
    except Exception as e:
        print(f"Table creation failed: {e}")
        sys.exit(1)
    
    try:
        test_sequential_caching()
        test_concurrent_caching()
        print("\nALL TESTS PASSED!")
    except Exception as e:
        print(f"\nTest Failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
