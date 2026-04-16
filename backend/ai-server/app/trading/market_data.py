import logging
from decimal import Decimal
from typing import Optional

from app.shared.infra.redis_client import redis_client

logger = logging.getLogger(__name__)


def get_current_price(ticker: str) -> Optional[Decimal]:
    """
    Redis에서 해당 종목의 실시간 체결가를 조회합니다.

    조회 우선순위:
    1) stocks:current:{ticker} -> price
    2) stocks:info:{ticker} -> currentPrice
    """
    r = redis_client.get_client()

    try:
        current_key = f"stocks:current:{ticker}"
        price_str = r.hget(current_key, "price")
        if price_str:
            return Decimal(str(price_str))

        info_key = f"stocks:info:{ticker}"
        price_str = r.hget(info_key, "currentPrice")
        if price_str:
            return Decimal(str(price_str))

        return None
    except Exception as exc:
        logger.error("Redis 시세 조회 실패 (%s): %s", ticker, exc)
        return None
