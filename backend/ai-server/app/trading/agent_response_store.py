from datetime import datetime
from typing import Any, Dict, List, Optional

from app.trading.constants import KST
from app.trading.core_api_client import _get_db_conn


def _ensure_table() -> None:
    query = """
        CREATE TABLE IF NOT EXISTS agent_response_status (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            trade_date DATE NOT NULL,
            user_id BIGINT NOT NULL,
            ticker VARCHAR(16) NOT NULL,
            strategy_slot VARCHAR(32) NOT NULL,
            news_received TINYINT(1) NOT NULL DEFAULT 0,
            quant_received TINYINT(1) NOT NULL DEFAULT 0,
            judge_received TINYINT(1) NOT NULL DEFAULT 0,
            news_received_at DATETIME NULL,
            quant_received_at DATETIME NULL,
            judge_received_at DATETIME NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_agent_response_status (trade_date, user_id, ticker, strategy_slot)
        )
    """
    with _get_db_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)


def mark_agent_response(
    *,
    user_id: Optional[int],
    ticker: str,
    strategy_slot: str,
    agent_type: str,
    trade_date: Optional[datetime] = None,
) -> None:
    if user_id is None:
        return

    _ensure_table()
    base_date = (trade_date or datetime.now(KST)).astimezone(KST).date()
    now = datetime.now(KST).replace(tzinfo=None)

    valid_agents = {
        "news": ("news_received", "news_received_at"),
        "quant": ("quant_received", "quant_received_at"),
        "judge": ("judge_received", "judge_received_at"),
    }
    if agent_type not in valid_agents:
        return

    flag_column, time_column = valid_agents[agent_type]
    query = f"""
        INSERT INTO agent_response_status (
            trade_date, user_id, ticker, strategy_slot, {flag_column}, {time_column}
        ) VALUES (%s, %s, %s, %s, 1, %s)
        ON DUPLICATE KEY UPDATE
            {flag_column} = 1,
            {time_column} = VALUES({time_column})
    """
    with _get_db_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (base_date, int(user_id), ticker, strategy_slot, now))


def list_agent_response_statuses(
    *,
    user_id: Optional[int] = None,
    trade_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    _ensure_table()
    if trade_date:
        base_date = datetime.fromisoformat(trade_date).date()
    else:
        base_date = datetime.now(KST).date()

    query = """
        SELECT
            trade_date,
            user_id,
            ticker,
            strategy_slot,
            news_received,
            quant_received,
            judge_received,
            news_received_at,
            quant_received_at,
            judge_received_at,
            updated_at
        FROM agent_response_status
        WHERE trade_date = %s
    """
    params: List[Any] = [base_date]
    if user_id is not None:
        query += " AND user_id = %s"
        params.append(int(user_id))
    query += " ORDER BY user_id ASC, ticker ASC, strategy_slot ASC"

    with _get_db_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall() or []

    return [
        {
            "tradeDate": str(row.get("trade_date")),
            "userId": int(row.get("user_id")),
            "ticker": str(row.get("ticker") or ""),
            "strategySlot": str(row.get("strategy_slot") or ""),
            "newsReceived": bool(row.get("news_received")),
            "quantReceived": bool(row.get("quant_received")),
            "judgeReceived": bool(row.get("judge_received")),
            "newsReceivedAt": row.get("news_received_at").isoformat() if row.get("news_received_at") else None,
            "quantReceivedAt": row.get("quant_received_at").isoformat() if row.get("quant_received_at") else None,
            "judgeReceivedAt": row.get("judge_received_at").isoformat() if row.get("judge_received_at") else None,
            "updatedAt": row.get("updated_at").isoformat() if row.get("updated_at") else None,
        }
        for row in rows
    ]
