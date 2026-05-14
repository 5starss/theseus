import json
import os
from datetime import date, datetime
from typing import Any, Dict, Optional

from collector.storage import get_storage_dir
from app.shared.infra.s3_client import s3_client
from app.trading.constants import KST
from app.trading.core_api_client import _get_db_conn


ANALYSIS_WORKFLOW_VERSION = "ticker_analysis_v1"


def _ensure_table() -> None:
    query = """
        CREATE TABLE IF NOT EXISTS ticker_analysis_cache (
            id BIGINT PRIMARY KEY AUTO_INCREMENT,
            trade_date DATE NOT NULL,
            ticker VARCHAR(16) NOT NULL,
            strategy_slot VARCHAR(32) NOT NULL,
            analysis_profile VARCHAR(64) NOT NULL,
            workflow_version VARCHAR(64) NOT NULL,
            status VARCHAR(32) NOT NULL,
            s3_key VARCHAR(512) NULL,
            local_path VARCHAR(1024) NULL,
            s3_uploaded TINYINT(1) NOT NULL DEFAULT 0,
            error_message TEXT NULL,
            generated_at DATETIME NULL,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uq_ticker_analysis_cache (
                trade_date, ticker, strategy_slot, analysis_profile, workflow_version
            )
        )
    """
    with _get_db_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query)


def current_trade_date() -> date:
    return datetime.now(KST).date()


def build_analysis_s3_key(
    *,
    trade_date: date,
    ticker: str,
    strategy_slot: str,
    analysis_profile: str,
    workflow_version: str = ANALYSIS_WORKFLOW_VERSION,
) -> str:
    day_path = trade_date.strftime("%Y/%m/%d")
    day_str = trade_date.strftime("%Y%m%d")
    filename = f"{ticker}_{strategy_slot}_{analysis_profile}_{workflow_version}_{day_str}.json"
    return f"ticker-analysis/{day_path}/{strategy_slot}/{filename}"


def _build_local_path(s3_key: str) -> str:
    storage_dir = get_storage_dir("ticker_analysis")
    return os.path.join(storage_dir, os.path.basename(s3_key))


def load_cache_row(
    *,
    ticker: str,
    strategy_slot: str,
    analysis_profile: str,
    trade_date: Optional[date] = None,
    workflow_version: str = ANALYSIS_WORKFLOW_VERSION,
) -> Optional[Dict[str, Any]]:
    _ensure_table()
    query = """
        SELECT *
        FROM ticker_analysis_cache
        WHERE trade_date = %s
          AND ticker = %s
          AND strategy_slot = %s
          AND analysis_profile = %s
          AND workflow_version = %s
        LIMIT 1
    """
    with _get_db_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                query,
                (
                    trade_date or current_trade_date(),
                    ticker,
                    strategy_slot,
                    analysis_profile,
                    workflow_version,
                ),
            )
            return cursor.fetchone()


def try_mark_running(
    *,
    ticker: str,
    strategy_slot: str,
    analysis_profile: str,
    trade_date: Optional[date] = None,
    workflow_version: str = ANALYSIS_WORKFLOW_VERSION,
) -> bool:
    _ensure_table()
    base_date = trade_date or current_trade_date()
    query = """
        INSERT IGNORE INTO ticker_analysis_cache (
            trade_date, ticker, strategy_slot, analysis_profile, workflow_version, status
        ) VALUES (%s, %s, %s, %s, %s, 'running')
    """
    with _get_db_conn() as conn:
        with conn.cursor() as cursor:
            affected = cursor.execute(
                query,
                (base_date, ticker, strategy_slot, analysis_profile, workflow_version),
            )
            if affected == 1:
                return True

            retry_query = """
                UPDATE ticker_analysis_cache
                SET status = 'running',
                    error_message = NULL,
                    s3_key = NULL,
                    local_path = NULL,
                    s3_uploaded = 0,
                    generated_at = NULL
                WHERE trade_date = %s
                  AND ticker = %s
                  AND strategy_slot = %s
                  AND analysis_profile = %s
                  AND workflow_version = %s
                  AND status = 'failed'
            """
            retried = cursor.execute(
                retry_query,
                (base_date, ticker, strategy_slot, analysis_profile, workflow_version),
            )
            return retried == 1


def save_completed(
    *,
    payload: Dict[str, Any],
    ticker: str,
    strategy_slot: str,
    analysis_profile: str,
    trade_date: Optional[date] = None,
    workflow_version: str = ANALYSIS_WORKFLOW_VERSION,
) -> Dict[str, Any]:
    _ensure_table()
    base_date = trade_date or current_trade_date()
    s3_key = build_analysis_s3_key(
        trade_date=base_date,
        ticker=ticker,
        strategy_slot=strategy_slot,
        analysis_profile=analysis_profile,
        workflow_version=workflow_version,
    )
    local_path = _build_local_path(s3_key)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    with open(local_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    uploaded = s3_client.upload_file(local_path, s3_key)

    now = datetime.now(KST).replace(tzinfo=None)
    query = """
        UPDATE ticker_analysis_cache
        SET status = 'completed',
            s3_key = %s,
            local_path = %s,
            s3_uploaded = %s,
            error_message = NULL,
            generated_at = %s
        WHERE trade_date = %s
          AND ticker = %s
          AND strategy_slot = %s
          AND analysis_profile = %s
          AND workflow_version = %s
    """
    with _get_db_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                query,
                (
                    s3_key,
                    local_path,
                    1 if uploaded else 0,
                    now,
                    base_date,
                    ticker,
                    strategy_slot,
                    analysis_profile,
                    workflow_version,
                ),
            )
    return {"s3_key": s3_key, "local_path": local_path, "s3_uploaded": uploaded}


def save_failed(
    *,
    ticker: str,
    strategy_slot: str,
    analysis_profile: str,
    error: Exception,
    trade_date: Optional[date] = None,
    workflow_version: str = ANALYSIS_WORKFLOW_VERSION,
) -> None:
    _ensure_table()
    query = """
        UPDATE ticker_analysis_cache
        SET status = 'failed',
            error_message = %s
        WHERE trade_date = %s
          AND ticker = %s
          AND strategy_slot = %s
          AND analysis_profile = %s
          AND workflow_version = %s
    """
    with _get_db_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                query,
                (
                    str(error),
                    trade_date or current_trade_date(),
                    ticker,
                    strategy_slot,
                    analysis_profile,
                    workflow_version,
                ),
            )


def load_payload(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    local_path = str(row.get("local_path") or "")
    s3_key = str(row.get("s3_key") or "")

    if local_path and os.path.exists(local_path):
        with open(local_path, "r", encoding="utf-8") as f:
            return json.load(f)

    if not s3_key:
        return None

    local_path = _build_local_path(s3_key)
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    if not s3_client.download_file(s3_key, local_path):
        return None
    with open(local_path, "r", encoding="utf-8") as f:
        return json.load(f)
