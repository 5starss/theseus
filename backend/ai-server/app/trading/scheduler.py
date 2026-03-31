import logging
import os
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.shared.infra.redis_client import redis_client
from app.trading.batch_feature_generator import run_daily_batch_preparation, run_news_rag_batch, run_quant_feature_batch
from app.trading.auto_trade import auto_trade_service
from app.trading.constants import KST, REDIS_BATCH_READY_PREFIX, STRATEGY_CACHE_TTL_SECONDS
from app.trading.monitoring import process_saved_strategies, sync_pending_strategy_archives

logger = logging.getLogger(__name__)
MORNING_STRATEGY_HOUR = 9
MORNING_STRATEGY_MINUTE = 0

class BatchScheduler:
    """
    정기 배치 작업(퀀트 feature, 뉴스/RAG, 자동매매)을 자동화하는 스케줄러.
    """
    
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.data_dir = os.getenv("QUANT_DATA_DIR", "storage/quant/data_cybos")
        self.auto_trade_interval_minutes = max(1, int(os.getenv("AUTOTRADE_INTERVAL_MINUTES", "5")))
        self.strategy_monitor_interval_seconds = max(15, int(os.getenv("AUTOTRADE_MONITOR_INTERVAL_SECONDS", "15")))

    @staticmethod
    def _batch_ready_key(batch_type: str, base_time: datetime | None = None) -> str:
        day_str = (base_time or datetime.now(KST)).astimezone(KST).strftime("%Y%m%d")
        return f"{REDIS_BATCH_READY_PREFIX}:{day_str}:{batch_type}"

    def mark_batch_ready(self, batch_type: str, *, base_time: datetime | None = None) -> None:
        r = redis_client.get_client()
        key = self._batch_ready_key(batch_type, base_time=base_time)
        r.set(key, "1")
        r.expire(key, STRATEGY_CACHE_TTL_SECONDS)
        logger.info("[Job] 배치 준비 완료 플래그 설정 (%s): %s", batch_type, key)

    def mark_today_batch_ready(self, batch_type: str) -> None:
        self.mark_batch_ready(batch_type)

    def is_today_batch_ready(self, batch_type: str) -> bool:
        try:
            return bool(redis_client.get_client().get(self._batch_ready_key(batch_type)))
        except Exception as exc:
            logger.error("[Job] 배치 준비 상태 조회 실패 (%s): %s", batch_type, exc)
            return False

    def is_today_quant_ready(self) -> bool:
        return self.is_today_batch_ready("quant")

    def is_today_news_ready(self) -> bool:
        return self.is_today_batch_ready("news")

    def is_today_strategy_ready(self) -> bool:
        return self.is_today_quant_ready() and self.is_today_news_ready()

    @staticmethod
    def _delay_until(hour: int, minute: int) -> int:
        now = datetime.now(KST)
        target_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return max(0, int((target_time - now).total_seconds()))

    def _schedule_morning_strategy_generation(self, job_id: str) -> None:
        self.schedule_global_generation(
            job_id,
            delay_seconds=self._delay_until(MORNING_STRATEGY_HOUR, MORNING_STRATEGY_MINUTE),
        )

    @staticmethod
    def _is_batch_success(result: dict) -> bool:
        return result.get("status") in ("ok", "partial")

    def run_batch_prepare(self, *, days: int) -> dict:
        result = run_daily_batch_preparation(data_dir=self.data_dir, days=days)
        if self._is_batch_success(result):
            self.mark_today_batch_ready("quant")
            self.mark_today_batch_ready("news")
        return result

    def run_news_batch_prepare(self) -> dict:
        result = run_news_rag_batch()
        if self._is_batch_success(result):
            self.mark_today_batch_ready("news")
        return result

    def run_quant_batch_prepare(self, *, days: int, ready_for_time: datetime | None = None) -> dict:
        result = run_quant_feature_batch(data_dir=self.data_dir, days=days)
        if self._is_batch_success(result):
            self.mark_batch_ready("quant", base_time=ready_for_time)
        return result

    def schedule_user_generation(self, user_id: int, delay_minutes: int = 0):
        """특정 사용자의 전략 생성을 APScheduler를 통해 예약합니다."""
        run_date = datetime.now(KST) + timedelta(minutes=delay_minutes)
        self.scheduler.add_job(
            auto_trade_service.run_user_cycle,
            trigger="date",
            run_date=run_date,
            args=[user_id],
            id=f"strategy_gen_user_{user_id}_{int(run_date.timestamp())}",
            replace_existing=True
        )
        logger.info("[Job] 사용자 %s의 전략 생성 작업을 %s 분 뒤(%s)에 예약했습니다.", user_id, delay_minutes, run_date)

    def schedule_global_generation(
        self,
        job_id: str,
        *,
        delay_seconds: int = 0,
        force: bool = False,
        force_refresh: bool = False,
    ) -> None:
        run_date = datetime.now(KST) + timedelta(seconds=delay_seconds)
        self.scheduler.add_job(
            auto_trade_service.run_enabled_users_cycle,
            trigger="date",
            run_date=run_date,
            kwargs={"force": force, "force_refresh": force_refresh},
            id=job_id,
            replace_existing=True,
        )
        logger.info(
            "[Job] 활성 사용자 전역 전략 생성 작업을 예약했습니다. (job_id=%s, run_date=%s, force=%s, force_refresh=%s)",
            job_id,
            run_date,
            force,
            force_refresh,
        )

    def start(self):
        """스케줄러 시작"""
        # 1. 장 마감 후 퀀트 feature 배치 (17:00)
        self.scheduler.add_job(
            self._evening_quant_batch,
            CronTrigger(hour=17, minute=0),
            id="evening_quant_batch",
            replace_existing=True
        )

        # 2. 익일 장전 뉴스/RAG 배치 (08:00)
        self.scheduler.add_job(
            self._morning_news_batch,
            CronTrigger(hour=8, minute=0),
            id="morning_news_batch",
            replace_existing=True
        )

        # 3. 08:20에 미완료 뉴스 배치 재시도
        self.scheduler.add_job(
            self._morning_retry_batch,
            CronTrigger(hour=8, minute=20),
            id="morning_retry_batch",
            replace_existing=True
        )

        # 4. 장중 신규 뉴스 반영용 정오 뉴스/RAG 배치 (12:00)
        self.scheduler.add_job(
            self._midday_news_batch,
            CronTrigger(hour=12, minute=0),
            id="midday_news_batch",
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
            "APScheduler 시작 완료 (17:00 퀀트 배치, 08:00 뉴스 배치, 08:20 뉴스 재시도, 12:00 뉴스 재배치, 자동매매 %s분 간격, 전략 모니터링 %s초 간격)",
            self.auto_trade_interval_minutes,
            self.strategy_monitor_interval_seconds,
        )

    def _evening_quant_batch(self):
        logger.info("[Job] 오후 17:00 퀀트 feature 배치 시작...")
        try:
            next_day = datetime.now(KST) + timedelta(days=1)
            self.run_quant_batch_prepare(days=730, ready_for_time=next_day)
            logger.info("[Job] 퀀트 feature 배치 작업 성공적으로 완료")
        except Exception as e:
            logger.error("[Job] 퀀트 feature 배치 실패: %s", e)

    def _morning_news_batch(self):
        logger.info("[Job] 오전 08:00 뉴스/RAG 배치 시작...")
        try:
            result = self.run_news_batch_prepare()
            logger.info("[Job] 뉴스/RAG 배치 완료 (status=%s)", result.get("status"))
            if self.is_today_strategy_ready():
                logger.info("[Job] 모든 배치가 완료되어 오전 09:00 전략 생성을 예약합니다.")
                self._schedule_morning_strategy_generation("post_morning_batch_generation")
        except Exception as e:
            logger.error("[Job] 뉴스/RAG 배치 실패: %s", e)

    def _morning_retry_batch(self):
        quant_ready = self.is_today_quant_ready()
        news_ready = self.is_today_news_ready()
        if quant_ready and news_ready:
            logger.info("[Job] 오전 08:20 재시도 스킵: 뉴스/퀀트 배치가 모두 완료되었습니다.")
            return
        logger.warning(
            "[Job] 오전 08:20 재시도: 미완료 배치를 재시도합니다. (quant_ready=%s, news_ready=%s)",
            quant_ready,
            news_ready,
        )
        if not quant_ready:
            try:
                self.run_quant_batch_prepare(days=730)
                logger.info("[Job] 오전 08:20 퀀트 feature 재시도 완료")
            except Exception as e:
                logger.error("[Job] 오전 08:20 퀀트 feature 재시도 실패: %s", e)
        if not news_ready:
            try:
                result = self.run_news_batch_prepare()
                logger.info("[Job] 오전 08:20 뉴스/RAG 재시도 완료")
            except Exception as e:
                logger.error("[Job] 오전 08:20 뉴스/RAG 재시도 실패: %s", e)
        if self.is_today_strategy_ready():
            logger.info("[Job] 오전 08:20 재시도 후 모든 배치가 완료되어 오전 09:00 전략 생성을 예약합니다.")
            self._schedule_morning_strategy_generation("post_retry_batch_generation")

    def _midday_news_batch(self):
        logger.info("[Job] 오후 12:00 뉴스/RAG 배치 시작...")
        try:
            result = self.run_news_batch_prepare()
            logger.info("[Job] 오후 12:00 뉴스/RAG 배치 작업 성공적으로 완료")
            if self.is_today_strategy_ready():
                logger.info("[Job] 12:00 뉴스 배치 완료로 활성 사용자 전역 전략 생성을 예약합니다.")
                self.schedule_global_generation("post_midday_batch_generation")
        except Exception as e:
            logger.error("[Job] 오후 12:00 뉴스/RAG 배치 실패: %s", e)

    def _auto_trade_cycle(self):
        # 5분 주기 로직: 전략 생성은 제거하고 아카이브 S3 동기화 등 보조 작업만 유지
        try:
            sync_result = sync_pending_strategy_archives()
            if sync_result.get("synced_count"):
                logger.info(
                    "[Job] 전략 아카이브 S3 동기화 완료: synced=%s failed=%s",
                    sync_result.get("synced_count"),
                    sync_result.get("failure_count"),
                )
            logger.debug("[Job] 주기적 백그라운드 작업 완료 (Sync)")
        except Exception as e:
            logger.error("[Job] 자동매매 주기적 보조 작업(S3 Sync) 실패: %s", e)

    def _strategy_monitor_cycle(self):
        try:
            if not auto_trade_service.is_market_session_open():
                logger.debug("[Job] 장 마감 상태라 전략 모니터링을 건너뜁니다.")
                return
            if not self.is_today_strategy_ready():
                logger.debug(
                    "[Job] 배치 미완료로 전략 모니터링을 건너뜁니다. (quant_ready=%s, news_ready=%s)",
                    self.is_today_quant_ready(),
                    self.is_today_news_ready(),
                )
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
