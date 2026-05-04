import logging
import os
import threading
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, time, timedelta
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from collector.storage import get_storage_dir
from app.shared.infra.redis_client import redis_client
from app.trading.orchestrator import orchestrate_trading
from app.shared.infra.s3_client import s3_client
from app.trading.autotrade_config_store import (
    list_config_payloads,
    load_config_payload,
    save_config_payload,
)
from app.trading.constants import (
    KST,
    REDIS_AUTOTRADE_TICKER_SNAPSHOT_PREFIX,
    STRATEGY_CACHE_TTL_SECONDS,
)
from app.trading.core_api_client import get_watchlists
from app.trading.strategy_store import (
    build_strategy_archive_paths,
    get_strategy_key_for_slot,
    load_strategy_payload,
    save_strategy_payload,
    write_json,
)

logger = logging.getLogger(__name__)

AutoTradeStyle = Literal["LONG", "SHORT"]
AccountType = Literal["AI", "USER"]
DEFAULT_AUTOTRADE_TICKERS = ["005930"]


class AutoTradeConfig(BaseModel):
    user_id: int = Field(..., description="자동매매 대상 사용자 ID")
    enabled: bool = Field(default=False, description="자동매매 활성화 여부")
    invest_style: AutoTradeStyle = Field(default="LONG", description="LONG=장투, SHORT=단타")
    account_type: AccountType = Field(default="AI", description="주문에 사용할 계좌 타입")
    tickers: List[str] = Field(default_factory=list, description="자동매매 대상 종목 목록")
    max_tickers_per_cycle: int = Field(default=3, ge=1, le=20, description="1회 실행 시 최대 종목 수")


class AutoTradeConfigRequest(BaseModel):
    enabled: bool = Field(..., description="자동매매 활성화 여부")
    invest_style: AutoTradeStyle = Field(default="LONG", description="LONG=장투, SHORT=단타")
    account_type: AccountType = Field(default="AI", description="주문에 사용할 계좌 타입")
    tickers: List[str] = Field(default_factory=list, description="자동매매 대상 종목 목록")
    max_tickers_per_cycle: int = Field(default=3, ge=1, le=20, description="1회 실행 시 최대 종목 수")


class AutoTradeService:
    def __init__(self):
        self._lock = threading.Lock()
        self._configs: Dict[int, AutoTradeConfig] = {}
        self._configs_loaded = False
        self._user_run_locks: Dict[int, threading.Lock] = {}
        self._max_parallel_users = max(1, int(os.getenv("AUTOTRADE_MAX_PARALLEL_USERS", "4")))

    def upsert_config(self, user_id: int, request: AutoTradeConfigRequest) -> AutoTradeConfig:
        config = AutoTradeConfig(user_id=user_id, **request.model_dump())
        with self._lock:
            self._configs[user_id] = config
        save_config_payload(config.user_id, config.model_dump())
        logger.info(
            "자동매매 설정 저장 - user_id=%s enabled=%s style=%s account_type=%s tickers=%s",
            user_id,
            config.enabled,
            config.invest_style,
            config.account_type,
            config.tickers,
        )
        return config

    @staticmethod
    def _current_strategy_slot(base_time: datetime | None = None) -> str:
        now = (base_time or datetime.now(KST)).astimezone(KST)
        return "morning" if now.time() < time(12, 0) else "afternoon"

    def _get_existing_slot_strategy(self, *, user_id: int, strategy_slot: str) -> Dict[str, Any] | None:
        redis_key = get_strategy_key_for_slot(
            user_id=user_id,
            day=datetime.now(KST),
            strategy_slot=strategy_slot,
        )
        if not redis_key:
            return None
        try:
            payload = load_strategy_payload(redis_key)
        except Exception:
            return None

        generated_at_raw = payload.get("generated_at")
        payload_slot = str(payload.get("strategy_slot") or "").strip()
        payload_user_id = payload.get("user_id")
        decisions = payload.get("decisions")

        try:
            generated_at = datetime.fromisoformat(str(generated_at_raw)).astimezone(KST)
        except Exception:
            return None

        if generated_at.date() != datetime.now(KST).date():
            return None

        if payload_slot != strategy_slot or payload_user_id != user_id:
            return None

        if not isinstance(decisions, list) or not decisions:
            return None

        valid_decisions = [
            decision for decision in decisions
            if isinstance(decision, dict) and isinstance(decision.get("judge_decision"), dict)
        ]
        if not valid_decisions:
            return None

        return payload

    def get_config(self, user_id: int) -> AutoTradeConfig:
        with self._lock:
            existing = self._configs.get(user_id)
        if existing:
            return existing

        persisted = load_config_payload(user_id)
        if persisted is not None:
            config = AutoTradeConfig(**persisted)
            with self._lock:
                self._configs[user_id] = config
            return config

        return AutoTradeConfig(user_id=user_id)

    def _get_user_run_lock(self, user_id: int) -> threading.Lock:
        with self._lock:
            existing = self._user_run_locks.get(user_id)
            if existing is not None:
                return existing
            lock = threading.Lock()
            self._user_run_locks[user_id] = lock
            return lock

    def list_configs(self) -> List[AutoTradeConfig]:
        with self._lock:
            if self._configs_loaded:
                return list(self._configs.values())
        
        configs_from_store = list_config_payloads()
        new_configs = {}
        for payload in configs_from_store:
            try:
                config = AutoTradeConfig(**payload)
                new_configs[config.user_id] = config
            except Exception as exc:
                logger.error("설정 파싱 실패: %s", exc)

        with self._lock:
            self._configs.update(new_configs)
            self._configs_loaded = True
            return list(self._configs.values())

    def _default_tickers_for_style(self, style: AutoTradeStyle) -> List[str]:
        env_key = "AUTOTRADE_LONG_TICKERS" if style == "LONG" else "AUTOTRADE_SHORT_TICKERS"
        raw = os.getenv(env_key, "").strip()
        if raw:
            return [ticker.strip() for ticker in raw.split(",") if ticker.strip()]
        return DEFAULT_AUTOTRADE_TICKERS.copy()

    @staticmethod
    def _sanitize_tickers(tickers: List[str], *, limit: int) -> List[str]:
        sanitized = []
        for ticker in tickers:
            ticker = str(ticker).strip()
            if len(ticker) == 6 and ticker.isdigit() and ticker not in sanitized:
                sanitized.append(ticker)
            if len(sanitized) >= limit:
                break
        return sanitized

    def _watchlist_tickers(self, user_id: int, *, limit: int) -> List[str]:
        try:
            watchlists = get_watchlists(user_id=user_id)
            tickers = [str(item.get("ticker") or "").strip() for item in watchlists if isinstance(item, dict)]
            return self._sanitize_tickers(tickers, limit=limit)
        except Exception as exc:
            logger.error("관심종목 조회 실패 - user_id=%s error=%s", user_id, exc)
            return []

    @staticmethod
    def _daily_ticker_snapshot_key(user_id: int, *, base_time: datetime | None = None) -> str:
        day_str = (base_time or datetime.now(KST)).astimezone(KST).strftime("%Y%m%d")
        return f"{REDIS_AUTOTRADE_TICKER_SNAPSHOT_PREFIX}:{day_str}:user_{user_id}"

    def _load_daily_ticker_snapshot(self, user_id: int, *, limit: int) -> List[str] | None:
        raw = redis_client.get_client().get(self._daily_ticker_snapshot_key(user_id))
        if not raw:
            return None
        try:
            payload = json.loads(raw)
            tickers = payload.get("tickers")
            if not isinstance(tickers, list): return None
            return self._sanitize_tickers(tickers, limit=limit)
        except Exception:
            return None

    def _save_daily_ticker_snapshot(self, user_id: int, tickers: List[str], *, source: str) -> None:
        payload = {
            "user_id": user_id,
            "date": datetime.now(KST).strftime("%Y-%m-%d"),
            "source": source,
            "tickers": tickers,
            "saved_at": datetime.now(KST).isoformat(),
        }
        key = self._daily_ticker_snapshot_key(user_id)
        redis_client.get_client().set(key, json.dumps(payload, ensure_ascii=False))
        redis_client.get_client().expire(key, STRATEGY_CACHE_TTL_SECONDS)

    def _resolve_current_tickers(self, config: AutoTradeConfig) -> tuple[List[str], str]:
        explicit = self._sanitize_tickers(config.tickers, limit=config.max_tickers_per_cycle)
        if explicit: return explicit, "config"
        watchlist_tickers = self._watchlist_tickers(config.user_id, limit=config.max_tickers_per_cycle)
        if watchlist_tickers: return watchlist_tickers, "watchlist"
        fallback = self._sanitize_tickers(self._default_tickers_for_style(config.invest_style), limit=config.max_tickers_per_cycle)
        return fallback, "default"

    def resolve_tickers(self, config: AutoTradeConfig) -> List[str]:
        frozen = self._load_daily_ticker_snapshot(config.user_id, limit=config.max_tickers_per_cycle)
        if frozen: return frozen
        resolved, source = self._resolve_current_tickers(config)
        self._save_daily_ticker_snapshot(config.user_id, resolved, source=source)
        return resolved

    @staticmethod
    def _is_market_session_open() -> bool:
        now = datetime.now(KST)
        if now.weekday() >= 5: return False
        current_time = now.time()
        return time(9, 0) <= current_time <= time(15, 30)

    def is_market_session_open(self) -> bool:
        return self._is_market_session_open()

    def _persist_cycle_decision(self, *, config: AutoTradeConfig, tickers: List[str], decisions: List[Dict[str, Any]]) -> Dict[str, Any]:
        now = datetime.now(KST)
        trade_storage_dir = get_storage_dir("trade")
        archive_paths = build_strategy_archive_paths(user_id=config.user_id, generated_at=now)
        local_path = os.path.join(trade_storage_dir, archive_paths["filename"])
        payload = {
            "schema": "judge_cycle_v1",
            "generated_at": now.isoformat(),
            "strategy_slot": self._current_strategy_slot(now),
            "user_id": config.user_id,
            "enabled": config.enabled,
            "invest_style": config.invest_style,
            "account_type": config.account_type,
            "tickers": tickers,
            "decisions": decisions,
            "archive": {
                "local_path": local_path,
                "s3_key": archive_paths["s3_key"],
                "s3_uploaded": False,
                "redis_key": archive_paths["redis_key"],
            },
        }
        write_json(local_path, payload)
        uploaded = s3_client.upload_file(local_path, archive_paths["s3_key"])
        payload["archive"]["s3_uploaded"] = uploaded
        write_json(local_path, payload)
        try:
            save_strategy_payload(archive_paths["redis_key"], payload, keep_index=True)
        except Exception as exc:
            logger.error("Redis 저장 실패: %s", exc)
        return payload["archive"]

    def run_user_cycle(self, user_id: int, *, force: bool = False, force_refresh: bool = False) -> Dict[str, Any]:
        user_lock = self._get_user_run_lock(user_id)
        if not user_lock.acquire(blocking=False):
            return {"status": "skipped", "reason": "user_cycle_in_progress", "user_id": user_id}
        try:
            config = self.get_config(user_id)
            if not config.enabled and not force:
                return {"status": "skipped", "reason": "autotrade_disabled", "user_id": user_id}
            if not force and not self._is_market_session_open():
                return {"status": "skipped", "reason": "market_closed", "user_id": user_id}
            strategy_slot = self._current_strategy_slot()
            if not force_refresh:
                existing = self._get_existing_slot_strategy(user_id=user_id, strategy_slot=strategy_slot)
                if existing:
                    return {"status": "ok", "message": "strategy_already_exists", "user_id": user_id, "strategy_slot": strategy_slot, "decision_archive": existing.get("archive")}
            tickers = self.resolve_tickers(config)
            if not tickers:
                return {"status": "skipped", "reason": "no_tickers", "user_id": user_id}
            
            results = []
            decision_records = []
            for ticker in tickers:
                try:
                    order_card = orchestrate_trading(ticker=ticker, user_id=user_id, account_type=config.account_type, invest_style=config.invest_style, execute_immediately=True, strategy_slot=strategy_slot)
                    results.append({"ticker": ticker, "action": order_card.get("order", {}).get("action"), "quantity": order_card.get("order", {}).get("quantity")})
                    decision_records.append({"ticker": ticker, "judge_decision": order_card})
                except Exception as exc:
                    logger.error("[%s] 실패: %s", ticker, exc)
                    results.append({"ticker": ticker, "status": "failed", "error": str(exc)})
            
            if not any("judge_decision" in d for d in decision_records):
                try:
                    from app.trading.scheduler_instance import scheduler
                    scheduler.schedule_user_generation(user_id, delay_minutes=5)
                except: pass
                return {"status": "failed", "reason": "no_valid_decisions", "results": results}
            
            archive = self._persist_cycle_decision(config=config, tickers=tickers, decisions=decision_records)
            return {"status": "ok", "user_id": user_id, "strategy_slot": strategy_slot, "decision_archive": archive, "results": results}
        except Exception as exc:
            logger.error("run_user_cycle 에러: %s", exc)
            try:
                from app.trading.scheduler_instance import scheduler
                scheduler.schedule_user_generation(user_id, delay_minutes=5)
            except: pass
            raise
        finally:
            user_lock.release()

    def enable_and_prepare(self, user_id: int, request: AutoTradeConfigRequest) -> Dict[str, Any]:
        config = self.upsert_config(user_id, request)
        response: Dict[str, Any] = {"status": "ok", "config": config.model_dump()}
        if config.enabled:
            try:
                from app.trading.scheduler_instance import scheduler
                if scheduler.is_today_strategy_ready():
                    scheduler.schedule_user_generation(user_id, delay_minutes=0)
                    response["bootstrap"] = {"status": "scheduled", "message": "즉시 전략 생성 스케줄러를 등록했습니다."}
            except Exception as e:
                logger.error("스케줄러 등록 실패: %s", e)
        return response

    def run_enabled_users_cycle(self, *, force: bool = False, force_refresh: bool = False) -> Dict[str, Any]:
        configs = [c for c in self.list_configs() if c.enabled]
        if not configs: return {"status": "ok", "message": "no_enabled_users"}
        max_workers = min(self._max_parallel_users, len(configs))
        results = []
        with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="autotrade") as executor:
            futures = {
                executor.submit(self.run_user_cycle, c.user_id, force=force, force_refresh=force_refresh): c.user_id
                for c in configs
            }
            for future in as_completed(futures):
                try: results.append(future.result())
                except Exception as e: results.append({"status": "failed", "error": str(e)})
        return {"status": "ok", "results": results}

auto_trade_service = AutoTradeService()
