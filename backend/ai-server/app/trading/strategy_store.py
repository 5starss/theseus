import json
import os
from datetime import datetime
from typing import Any, Dict

from app.shared.infra.redis_client import redis_client
from app.trading.constants import KST, REDIS_STRATEGY_INDEX_PREFIX, REDIS_STRATEGY_PAYLOAD_PREFIX, STRATEGY_CACHE_TTL_SECONDS


def write_json(local_path: str, payload: Dict[str, Any]) -> None:
    with open(local_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def build_strategy_archive_paths(*, user_id: int, generated_at: datetime) -> Dict[str, str]:
    day_str = generated_at.astimezone(KST).strftime("%Y%m%d")
    ts_str = generated_at.astimezone(KST).strftime("%Y%m%d_%H%M%S")
    filename = f"judge_cycle_user_{user_id}_{ts_str}.json"
    return {
        "day_str": day_str,
        "ts_str": ts_str,
        "filename": filename,
        "s3_key": f"judge-decisions/{day_str}/user_{user_id}/{filename}",
        "redis_key": f"{REDIS_STRATEGY_PAYLOAD_PREFIX}:{day_str}:user_{user_id}:{ts_str}",
        "redis_index_key": f"{REDIS_STRATEGY_INDEX_PREFIX}:{day_str}",
    }


def strategy_index_key_for_day(day: datetime) -> str:
    return f"{REDIS_STRATEGY_INDEX_PREFIX}:{day.astimezone(KST).strftime('%Y%m%d')}"


def strategy_index_key_for_today() -> str:
    return strategy_index_key_for_day(datetime.now(KST))


def strategy_slot_ref_key(*, user_id: int, day: datetime, strategy_slot: str) -> str:
    day_str = day.astimezone(KST).strftime("%Y%m%d")
    return f"{REDIS_STRATEGY_INDEX_PREFIX}:{day_str}:slot:{strategy_slot}:user_{user_id}"


def load_strategy_payload(redis_key: str) -> Dict[str, Any]:
    raw = redis_client.get_client().get(redis_key)
    if not raw:
        raise FileNotFoundError(f"Redis strategy payload not found: {redis_key}")
    return json.loads(raw)


def get_strategy_key_for_slot(*, user_id: int, day: datetime, strategy_slot: str) -> str | None:
    return redis_client.get_client().get(
        strategy_slot_ref_key(user_id=user_id, day=day, strategy_slot=strategy_slot)
    )


def save_strategy_payload(redis_key: str, payload: Dict[str, Any], *, keep_index: bool = False) -> None:
    r = redis_client.get_client()
    r.set(redis_key, json.dumps(payload, ensure_ascii=False))
    r.expire(redis_key, STRATEGY_CACHE_TTL_SECONDS)

    if keep_index:
        generated_at = payload.get("generated_at")
        try:
            base_day = datetime.fromisoformat(str(generated_at))
        except Exception:
            base_day = datetime.now(KST)
        index_key = strategy_index_key_for_day(base_day)
        r.sadd(index_key, redis_key)
        r.expire(index_key, STRATEGY_CACHE_TTL_SECONDS)

        strategy_slot = str(payload.get("strategy_slot") or "").strip()
        user_id = payload.get("user_id")
        if strategy_slot and user_id is not None:
            slot_ref_key = strategy_slot_ref_key(
                user_id=int(user_id),
                day=base_day,
                strategy_slot=strategy_slot,
            )
            r.set(slot_ref_key, redis_key)
            r.expire(slot_ref_key, STRATEGY_CACHE_TTL_SECONDS)


def resolve_strategy_s3_key(payload: Dict[str, Any]) -> str:
    archive = payload.get("archive", {})
    if archive.get("s3_key"):
        return archive["s3_key"]

    generated_at = payload.get("generated_at") or datetime.now(KST).isoformat()
    try:
        generated_day = datetime.fromisoformat(str(generated_at))
    except Exception:
        generated_day = datetime.now(KST)
    day_str = generated_day.astimezone(KST).strftime("%Y%m%d")
    user_id = payload.get("user_id", "unknown")
    filename = os.path.basename(archive.get("local_path", f"judge_cycle_user_{user_id}_{day_str}.json"))
    return f"judge-decisions/{day_str}/user_{user_id}/{filename}"
