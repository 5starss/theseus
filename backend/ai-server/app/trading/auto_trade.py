import logging
import os
import threading
import json
from datetime import datetime, time
from typing import Any, Dict, List, Literal

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
            return load_strategy_payload(redis_key)
        except FileNotFoundError:
            return None

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

    def list_configs(self) -> List[AutoTradeConfig]:
        configs: List[AutoTradeConfig] = []
        restored: Dict[int, AutoTradeConfig] = {}
        for payload in list_config_payloads():
            try:
                config = AutoTradeConfig(**payload)
            except Exception as exc:
                logger.error("자동매매 설정 복원 실패 - payload=%s error=%s", payload, exc)
                continue
            configs.append(config)
            restored[config.user_id] = config

        if restored:
            with self._lock:
                self._configs.update(restored)
        return configs

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
        except Exception as exc:
            logger.error("관심종목 조회 실패 - user_id=%s error=%s", user_id, exc)
            return []

        tickers = [str(item.get("ticker") or "").strip() for item in watchlists if isinstance(item, dict)]
        return self._sanitize_tickers(tickers, limit=limit)

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
        except Exception as exc:
            logger.error("자동매매 종목 스냅샷 파싱 실패 - user_id=%s error=%s", user_id, exc)
            return None

        tickers = payload.get("tickers")
        if not isinstance(tickers, list):
            return None
        return self._sanitize_tickers(tickers, limit=limit)

    def _save_daily_ticker_snapshot(self, user_id: int, tickers: List[str], *, source: str) -> None:
        payload = {
            "user_id": user_id,
            "date": datetime.now(KST).strftime("%Y-%m-%d"),
            "source": source,
            "tickers": tickers,
            "saved_at": datetime.now(KST).isoformat(),
        }
        client = redis_client.get_client()
        key = self._daily_ticker_snapshot_key(user_id)
        client.set(key, json.dumps(payload, ensure_ascii=False))
        client.expire(key, STRATEGY_CACHE_TTL_SECONDS)

    def _resolve_current_tickers(self, config: AutoTradeConfig) -> tuple[List[str], str]:
        explicit = self._sanitize_tickers(config.tickers, limit=config.max_tickers_per_cycle)
        if explicit:
            return explicit, "config"

        watchlist_tickers = self._watchlist_tickers(config.user_id, limit=config.max_tickers_per_cycle)
        if watchlist_tickers:
            return watchlist_tickers, "watchlist"

        fallback = self._sanitize_tickers(
            self._default_tickers_for_style(config.invest_style),
            limit=config.max_tickers_per_cycle,
        )
        return fallback, "default"

    def resolve_tickers(self, config: AutoTradeConfig) -> List[str]:
        frozen = self._load_daily_ticker_snapshot(config.user_id, limit=config.max_tickers_per_cycle)
        if frozen:
            logger.info(
                "자동매매 대상 종목 결정 - user_id=%s source=daily_snapshot tickers=%s",
                config.user_id,
                frozen,
            )
            return frozen

        resolved, source = self._resolve_current_tickers(config)
        self._save_daily_ticker_snapshot(config.user_id, resolved, source=source)
        logger.info(
            "자동매매 대상 종목 결정 - user_id=%s source=%s tickers=%s",
            config.user_id,
            source,
            resolved,
        )
        return resolved

    @staticmethod
    def _is_market_session_open() -> bool:
        now = datetime.now(KST)
        if now.weekday() >= 5:
            return False
        current_time = now.time()
        return time(9, 0) <= current_time <= time(15, 30)

    def is_market_session_open(self) -> bool:
        return self._is_market_session_open()

    def _persist_cycle_decision(
        self,
        *,
        config: AutoTradeConfig,
        tickers: List[str],
        decisions: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        now = datetime.now(KST)
        trade_storage_dir = get_storage_dir("trade")
        archive_paths = build_strategy_archive_paths(user_id=config.user_id, generated_at=now)
        filename = archive_paths["filename"]
        local_path = os.path.join(trade_storage_dir, filename)

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
            logger.error("자동매매 전략 Redis 캐시 저장 실패: %s", exc)

        return {
            "local_path": local_path,
            "s3_key": archive_paths["s3_key"],
            "s3_uploaded": uploaded,
            "redis_key": archive_paths["redis_key"],
        }

    def run_user_cycle(self, user_id: int, *, force: bool = False, force_refresh: bool = False) -> Dict[str, Any]:
        config = self.get_config(user_id)
        if not config.enabled and not force:
            return {"status": "skipped", "reason": "autotrade_disabled", "user_id": user_id}

        if not force and not self._is_market_session_open():
            return {"status": "skipped", "reason": "market_closed", "user_id": user_id}

        strategy_slot = self._current_strategy_slot()
        if not force_refresh:
            existing_payload = self._get_existing_slot_strategy(user_id=user_id, strategy_slot=strategy_slot)
            if existing_payload is not None:
                archive = existing_payload.get("archive", {})
                return {
                    "status": "ok",
                    "message": "strategy_already_exists",
                    "user_id": user_id,
                    "strategy_slot": strategy_slot,
                    "decision_archive": {
                        "local_path": archive.get("local_path"),
                        "s3_key": archive.get("s3_key"),
                        "s3_uploaded": archive.get("s3_uploaded"),
                        "redis_key": archive.get("redis_key"),
                    },
                }

        tickers = self.resolve_tickers(config)
        if not tickers:
            return {"status": "skipped", "reason": "no_tickers", "user_id": user_id}

        logger.info(
            "자동매매 전략 생성 시작 - user_id=%s strategy_slot=%s tickers=%s invest_style=%s",
            user_id,
            strategy_slot,
            tickers,
            config.invest_style,
        )

        results = []
        decision_records = []
        for ticker in tickers:
            try:
                order_card = orchestrate_trading(
                    ticker=ticker,
                    user_id=user_id,
                    account_type=config.account_type,
                    invest_style=config.invest_style,
                    execute_immediately=False,
                    strategy_slot=strategy_slot,
                )
                results.append(
                    {
                        "ticker": ticker,
                        "execution_status": order_card.get("execution_status"),
                        "action": order_card.get("order", {}).get("action"),
                        "quantity": order_card.get("order", {}).get("quantity"),
                    }
                )
                decision_records.append(
                    {
                        "ticker": ticker,
                        "judge_decision": order_card,
                    }
                )
            except Exception as exc:
                logger.error("자동매매 실행 실패 - user_id=%s ticker=%s error=%s", user_id, ticker, exc)
                results.append({"ticker": ticker, "status": "failed", "error": str(exc)})
                decision_records.append(
                    {
                        "ticker": ticker,
                        "error": str(exc),
                    }
                )

        persistence = self._persist_cycle_decision(
            config=config,
            tickers=tickers,
            decisions=decision_records,
        )

        return {
            "status": "ok",
            "user_id": user_id,
            "strategy_slot": strategy_slot,
            "enabled": config.enabled,
            "invest_style": config.invest_style,
            "account_type": config.account_type,
            "tickers": tickers,
            "results": results,
            "decision_archive": persistence,
        }

    def enable_and_prepare(self, user_id: int, request: AutoTradeConfigRequest) -> Dict[str, Any]:
        config = self.upsert_config(user_id, request)
        response: Dict[str, Any] = {"status": "ok", "config": config.model_dump()}
        if config.enabled:
            response["bootstrap"] = {
                "status": "skipped",
                "reason": "deferred_until_scheduled_cycle",
                "message": "당일 첫 전략 생성 시점에 자동매매 대상 종목 스냅샷을 확정합니다.",
            }
        return response

    def run_enabled_users_cycle(self) -> Dict[str, Any]:
        configs = [config for config in self.list_configs() if config.enabled]
        if not configs:
            return {"status": "ok", "message": "no_enabled_users", "run_count": 0}

        results = [self.run_user_cycle(config.user_id) for config in configs]
        logger.info("자동매매 주기 실행 완료 - enabled_users=%s", len(results))
        return {"status": "ok", "run_count": len(results), "results": results}


auto_trade_service = AutoTradeService()
