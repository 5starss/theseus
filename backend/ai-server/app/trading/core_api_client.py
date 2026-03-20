import os
import httpx
import logging
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
import pymysql
import pymysql.cursors

load_dotenv()
logger = logging.getLogger(__name__)

CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api-server:8081/api/v1")
AUTO_TRADE_USER_ID = os.getenv("AUTO_TRADE_USER_ID", "1") # Default bot user ID

def _get_user_id(user_id: Optional[int] = None) -> int:
    return int(user_id if user_id is not None else AUTO_TRADE_USER_ID)


def _get_db_conn():
    return pymysql.connect(
        host=os.getenv("DB_HOST") or os.getenv("MYSQL_HOST") or "mysql",
        port=int(os.getenv("DB_PORT") or os.getenv("MYSQL_PORT") or "3306"),
        user=os.getenv("DB_USER") or os.getenv("MYSQL_USER") or "root",
        password=os.getenv("DB_PASSWORD") or os.getenv("MYSQL_PASSWORD") or "",
        database=os.getenv("DB_DATABASE") or os.getenv("MYSQL_DATABASE") or "stock_db",
        cursorclass=pymysql.cursors.DictCursor,
        charset="utf8mb4",
        autocommit=True,
    )


def _request(
    method: str,
    path: str,
    *,
    user_id: Optional[int] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
) -> Any:
    url = f"{CORE_API_URL}{path}"
    headers = {"X-User-Id": str(_get_user_id(user_id))}
    if json is not None:
        headers["Content-Type"] = "application/json"

    try:
        response = httpx.request(
            method,
            url,
            headers=headers,
            params=params,
            json=json,
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("isSuccess"):
            return data.get("result", {})

        logger.error("Core API 비정상 응답 (%s %s): %s", method, path, data)
        return {}
    except httpx.RequestError as e:
        logger.error("Core API 호출 실패 (%s %s): %s", method, path, e)
        return {}
    except httpx.HTTPStatusError as e:
        logger.error(
            "Core API 상태 에러 (%s %s, %s): %s",
            method,
            path,
            e.response.status_code,
            e.response.text,
        )
        return {}


def get_account_summary(user_id: Optional[int] = None, account_type: str = "USER") -> Dict[str, Any]:
    """
    DB에서 계좌 요약 정보(예수금, 포트폴리오 등)를 직접 조회합니다.
    """
    resolved_user_id = _get_user_id(user_id)
    positions = get_positions(user_id=resolved_user_id, account_type=account_type)

    query = """
        SELECT
            account_id,
            dnca_tot_amt,
            available_amt,
            locked_amt
        FROM accounts
        WHERE user_id = %s
          AND account_type = %s
        LIMIT 1
    """
    with _get_db_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (resolved_user_id, account_type))
            row = cursor.fetchone()

    if not row:
        logger.error("DB 계좌 조회 실패 - user_id=%s account_type=%s", resolved_user_id, account_type)
        return {}

    total_amt = int(float(row.get("dnca_tot_amt") or 0))
    available_amt = int(float(row.get("available_amt") or 0))
    locked_amt = int(float(row.get("locked_amt") or 0))

    return {
        "accountId": row.get("account_id"),
        "totalAmt": total_amt,
        "availableAmt": available_amt,
        "lockedAmt": locked_amt,
        "positions": positions,
    }


def get_user_profile(user_id: Optional[int] = None) -> Dict[str, Any]:
    """
    DB에서 사용자 프로필(투자 성향 포함)을 직접 조회합니다.
    """
    resolved_user_id = _get_user_id(user_id)
    query = """
        SELECT
            user_id,
            email,
            nickname,
            investment_style
        FROM users
        WHERE user_id = %s
        LIMIT 1
    """
    with _get_db_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (resolved_user_id,))
            row = cursor.fetchone()

    if not row:
        logger.error("DB 사용자 조회 실패 - user_id=%s", resolved_user_id)
        return {}

    return {
        "userId": row.get("user_id"),
        "email": row.get("email"),
        "nickname": row.get("nickname"),
        "investmentStyle": row.get("investment_style"),
    }


def get_positions(user_id: Optional[int] = None, account_type: str = "USER") -> List[Dict[str, Any]]:
    """
    DB에서 보유 종목 목록을 직접 조회합니다.
    """
    resolved_user_id = _get_user_id(user_id)
    query = """
        SELECT
            p.ticker,
            p.quantity,
            p.available_quantity AS availableQuantity,
            p.locked_quantity AS lockedQuantity,
            p.average_price AS averagePrice,
            p.total_purchase_amount AS totalPurchaseAmount,
            s.company_name AS companyName
        FROM positions p
        JOIN accounts a
          ON a.account_id = p.account_id
        LEFT JOIN stocks s
          ON s.ticker = p.ticker
        WHERE a.user_id = %s
          AND a.account_type = %s
        ORDER BY p.ticker ASC
    """
    with _get_db_conn() as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (resolved_user_id, account_type))
            rows = cursor.fetchall() or []

    positions: List[Dict[str, Any]] = []
    for row in rows:
        positions.append(
            {
                "ticker": str(row.get("ticker") or ""),
                "quantity": int(row.get("quantity") or 0),
                "availableQuantity": int(row.get("availableQuantity") or 0),
                "lockedQuantity": int(row.get("lockedQuantity") or 0),
                "averagePrice": int(float(row.get("averagePrice") or 0)),
                "totalPurchaseAmount": int(float(row.get("totalPurchaseAmount") or 0)),
                "companyName": row.get("companyName") or str(row.get("ticker") or ""),
            }
        )
    return positions


def get_trading_account_snapshot(user_id: Optional[int] = None, account_type: str = "USER") -> Dict[str, Any]:
    """
    자동매매에 필요한 계좌 요약과 보유 종목 정보를 한 번에 정규화합니다.
    """
    summary = get_account_summary(user_id=user_id, account_type=account_type)
    positions = get_positions(user_id=user_id, account_type=account_type)

    quantity_map = {
        str(pos.get("ticker")): {
            "quantity": int(pos.get("quantity") or 0),
            "availableQuantity": int(pos.get("availableQuantity") or 0),
            "lockedQuantity": int(pos.get("lockedQuantity") or 0),
            "averagePrice": int(float(pos.get("averagePrice") or 0)),
            "companyName": pos.get("companyName"),
        }
        for pos in positions
        if pos.get("ticker")
    }

    merged_positions = []
    seen_tickers = set()
    for position in summary.get("positions", []) if isinstance(summary.get("positions"), list) else []:
        ticker = str(position.get("ticker") or "")
        holding = quantity_map.get(ticker, {})
        seen_tickers.add(ticker)
        merged_positions.append(
            {
                **position,
                "ticker": ticker,
                "quantity": int(position.get("quantity") or holding.get("quantity") or 0),
                "availableQuantity": int(holding.get("availableQuantity") or 0),
                "lockedQuantity": int(holding.get("lockedQuantity") or 0),
                "averagePrice": int(float(position.get("averagePrice") or holding.get("averagePrice") or 0)),
                "companyName": position.get("companyName") or holding.get("companyName") or ticker,
            }
        )

    for ticker, holding in quantity_map.items():
        if ticker in seen_tickers:
            continue

        merged_positions.append(
            {
                "ticker": ticker,
                "quantity": holding["quantity"],
                "availableQuantity": holding["availableQuantity"],
                "lockedQuantity": holding["lockedQuantity"],
                "averagePrice": holding["averagePrice"],
                "companyName": holding["companyName"] or ticker,
            }
        )

    summary["positions"] = merged_positions
    summary["availableAmt"] = int(float(summary.get("availableAmt") or 0))
    summary["lockedAmt"] = int(float(summary.get("lockedAmt") or 0))
    summary["totalAmt"] = int(float(summary.get("totalAmt") or 0))
    return summary


def execute_order(
    ticker: str,
    order_type: str,
    price: int,
    quantity: int,
    user_id: Optional[int] = None,
    account_type: str = "USER",
) -> bool:
    """
    Core API Server로 주문 요청을 전송합니다.
    """
    payload = {
        "ticker": ticker,
        "order_type": order_type.upper(), # BUY / SELL
        "price_type": "LIMIT", # 기본값으로 지정가 사용
        "account_type": account_type,
        "price": price,
        "quantity": quantity
    }

    result = _request("POST", "/orders", user_id=user_id, json=payload)
    success = bool(result)
    if success:
        logger.info("주문 실행 성공: %s %s %s주 @ %s원", ticker, order_type, quantity, price)
    return success
