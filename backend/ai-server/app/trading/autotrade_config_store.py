import json
import logging
from typing import List

from app.shared.infra.redis_client import redis_client
from app.trading.constants import (
    REDIS_AUTOTRADE_CONFIG_INDEX_KEY,
    REDIS_AUTOTRADE_CONFIG_PREFIX,
)

logger = logging.getLogger(__name__)


def config_redis_key(user_id: int) -> str:
    return f"{REDIS_AUTOTRADE_CONFIG_PREFIX}:user_{user_id}"


def save_config_payload(user_id: int, payload: dict) -> None:
    r = redis_client.get_client()
    redis_key = config_redis_key(user_id)
    r.set(redis_key, json.dumps(payload, ensure_ascii=False))
    r.sadd(REDIS_AUTOTRADE_CONFIG_INDEX_KEY, redis_key)


def load_config_payload(user_id: int) -> dict | None:
    raw = redis_client.get_client().get(config_redis_key(user_id))
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception as exc:
        logger.error("자동매매 설정 Redis 로드 실패 - user_id=%s error=%s", user_id, exc)
        return None


def list_config_payloads() -> List[dict]:
    r = redis_client.get_client()
    redis_keys = sorted(r.smembers(REDIS_AUTOTRADE_CONFIG_INDEX_KEY))
    payloads: List[dict] = []
    for redis_key in redis_keys:
        raw = r.get(redis_key)
        if not raw:
            r.srem(REDIS_AUTOTRADE_CONFIG_INDEX_KEY, redis_key)
            continue
        try:
            payloads.append(json.loads(raw))
        except Exception as exc:
            logger.error("자동매매 설정 Redis 파싱 실패 - key=%s error=%s", redis_key, exc)
    return payloads
