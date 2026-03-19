import os
import httpx
import logging
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

CORE_API_URL = os.getenv("CORE_API_URL", "http://core-api-server:8080/api/v1")
AUTO_TRADE_USER_ID = os.getenv("AUTO_TRADE_USER_ID", "1") # Default bot user ID

def _get_user_id(user_id: Optional[int] = None) -> str:
    return str(user_id if user_id is not None else AUTO_TRADE_USER_ID)


def _request(
    method: str,
    path: str,
    *,
    user_id: Optional[int] = None,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
) -> Any:
    url = f"{CORE_API_URL}{path}"
    headers = {"X-User-Id": _get_user_id(user_id)}
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
    Core API Server에서 계좌 요약 정보(예수금, 포트폴리오 등)를 조회합니다.
    """
    return _request(
        "GET",
        "/accounts/summary",
        user_id=user_id,
        params={"account_type": account_type},
    )


def get_positions(user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Core API Server에서 보유 종목 목록을 조회합니다.
    """
    result = _request("GET", "/positions", user_id=user_id)
    return result if isinstance(result, list) else []


def get_trading_account_snapshot(user_id: Optional[int] = None, account_type: str = "USER") -> Dict[str, Any]:
    """
    자동매매에 필요한 계좌 요약과 보유 종목 정보를 한 번에 정규화합니다.
    """
    summary = get_account_summary(user_id=user_id, account_type=account_type)
    positions = get_positions(user_id=user_id)

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
