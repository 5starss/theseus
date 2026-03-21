import logging
import os
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.shared.infra.redis_client import redis_client
from app.trading.batch_feature_generator import run_daily_batch_preparation
from app.trading.auto_trade import auto_trade_service
from app.trading.constants import KST, REDIS_BATCH_READY_PREFIX, STRATEGY_CACHE_TTL_SECONDS
from app.trading.monitoring import process_saved_strategies

logger = logging.getLogger(__name__)

class BatchScheduler:
    """
    정기 배치 작업(뉴스 수집 및 퀀트 피처 생성)만 자동화하는 스케줄러.
    """
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.data_dir = os.getenv("QUANT_DATA_DIR", "storage/quant/data_cybos")
        self.auto_trade_interval_minutes = max(1, int(os.getenv("AUTOTRADE_INTERVAL_MINUTES", "5")))
        self.strategy_monitor_interval_seconds = max(15, int(os.getenv("AUTOTRADE_MONITOR_INTERVAL_SECONDS", "15")))

    @staticmethod
    def _batch_ready_key(base_time: datetime | None = None) -> str:
        day_str = (base_time or datetime.now(KST)).astimezone(KST).strftime("%Y%m%d")
        return f"{REDIS_BATCH_READY_PREFIX}:{day_str}:morning"

    def mark_today_batch_ready(self) -> None:
        r = redis_client.get_client()
        key = self._batch_ready_key()
        r.set(key, "1")
        r.expire(key, STRATEGY_CACHE_TTL_SECONDS)
        logger.debug("[Job] 자동매매 배치 준비 완료 플래그 설정: %s", key)

    def is_today_batch_ready(self) -> bool:
        try:
            return bool(redis_client.get_client().get(self._batch_ready_key()))
        except Exception as exc:
            logger.error("[Job] 배치 준비 상태 조회 실패: %s", exc)
            return False

    def run_batch_prepare(self, *, days: int) -> dict:
        result = run_daily_batch_preparation(data_dir=self.data_dir, days=days)
        if result.get("status") == "ok":
            self.mark_today_batch_ready()
        return result

    def start(self):
        """스케줄러 시작"""
        # 1. 아침 전체 배치 (08:00) - 2년치(730일) 데이터 로드 및 뉴스 수집
        self.scheduler.add_job(
            self._morning_full_batch,
            CronTrigger(hour=8, minute=0),
            id="morning_full_batch",
            replace_existing=True
        )
        
        # 2. 오후 부분 배치 (12:00) - 금일(09시~) 데이터만 갱신 및 뉴스 갱신
        self.scheduler.add_job(
            self._afternoon_partial_batch,
            CronTrigger(hour=12, minute=0),
            id="afternoon_partial_batch",
            replace_existing=True
        )

        self.scheduler.add_job(
            self._auto_trade_cycle,
            "interval",
            minutes=self.auto_trade_interval_minutes,
            id="auto_trade_cycle",
            replace_existing=True,
        )

        self.scheduler.add_job(
            self._strategy_monitor_cycle,
            "interval",
            seconds=self.strategy_monitor_interval_seconds,
            id="strategy_monitor_cycle",
            replace_existing=True,
        )
        
        self.scheduler.start()
        logger.debug(
            "APScheduler 시작 완료 (08:00 전체 배치, 12:00 부분 배치, 자동매매 %s분 간격, 전략 모니터링 %s초 간격)",
            self.auto_trade_interval_minutes,
            self.strategy_monitor_interval_seconds,
        )

    def _morning_full_batch(self):
        logger.debug("[Job] 오전 08:00 전체 배치(RAG + Quant 2yr) 시작...")
        try:
            self.run_batch_prepare(days=730)
            logger.debug("[Job] 오전 배치 작업 성공적으로 완료")
        except Exception as e:
            logger.error("[Job] 오전 배치 실패: %s", e)

    def _afternoon_partial_batch(self):
        logger.debug("[Job] 오후 12:00 부분 배치(RAG + Quant Today) 시작...")
        try:
            self.run_batch_prepare(days=0)
            logger.debug("[Job] 오후 부분 배치 작업 성공적으로 완료")
        except Exception as e:
            logger.error("[Job] 오후 배치 실패: %s", e)

    def _auto_trade_cycle(self):
        try:
            if not auto_trade_service.is_market_session_open():
                logger.debug("[Job] 장 마감 상태라 자동매매 전략 생성을 건너뜁니다.")
                return
            if not self.is_today_batch_ready():
                logger.debug("[Job] 오전 데이터 배치가 아직 끝나지 않아 자동매매 전략 생성을 건너뜁니다.")
                return
            result = auto_trade_service.run_enabled_users_cycle()
            if result.get("message") == "no_enabled_users":
                logger.debug("[Job] 자동매매 활성 사용자 없음")
                return
            logger.debug("[Job] 자동매매 주기 실행 완료: %s", result)
        except Exception as e:
            logger.error("[Job] 자동매매 주기 실행 실패: %s", e)

    def _strategy_monitor_cycle(self):
        try:
            if not auto_trade_service.is_market_session_open():
                logger.debug("[Job] 장 마감 상태라 전략 모니터링을 건너뜁니다.")
                return
            if not self.is_today_batch_ready():
                logger.debug("[Job] 오전 데이터 배치가 아직 끝나지 않아 전략 모니터링을 건너뜁니다.")
                return
            result = process_saved_strategies()
            if result.get("message") == "no_strategy_files":
                enabled_count = len([config for config in auto_trade_service.list_configs() if config.enabled])
                if enabled_count > 0:
                    logger.warning("[Job] 활성 자동매매 사용자가 %s명인데 Redis 전략 캐시가 비어 있습니다.", enabled_count)
                    return
                logger.debug("[Job] 모니터링할 전략 파일 없음")
                return

            has_activity = any(item.get("changed") or item.get("processed") for item in result.get("results", []))
            if has_activity:
                logger.debug("[Job] 전략 모니터링 실행 완료: %s", result)
        except Exception as e:
            logger.error("[Job] 전략 모니터링 실행 실패: %s", e)

    def shutdown(self):
        self.scheduler.shutdown()
        logger.debug("BatchScheduler 종료")
