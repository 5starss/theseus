import logging
import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.trading.batch_feature_generator import run_daily_batch_preparation
from app.trading.auto_trade import auto_trade_service
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
        self.strategy_monitor_interval_minutes = max(1, int(os.getenv("AUTOTRADE_MONITOR_INTERVAL_MINUTES", "1")))

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
            minutes=self.strategy_monitor_interval_minutes,
            id="strategy_monitor_cycle",
            replace_existing=True,
        )
        
        self.scheduler.start()
        logger.info(
            "APScheduler 시작 완료 (08:00 전체 배치, 12:00 부분 배치, 자동매매 %s분 간격, 전략 모니터링 %s분 간격)",
            self.auto_trade_interval_minutes,
            self.strategy_monitor_interval_minutes,
        )

    def _morning_full_batch(self):
        logger.info("[Job] 오전 08:00 전체 배치(RAG + Quant 2yr) 시작...")
        try:
            run_daily_batch_preparation(data_dir=self.data_dir, days=730)
            logger.info("[Job] 오전 배치 작업 성공적으로 완료")
        except Exception as e:
            logger.error("[Job] 오전 배치 실패: %s", e)

    def _afternoon_partial_batch(self):
        logger.info("[Job] 오후 12:00 부분 배치(RAG + Quant Today) 시작...")
        try:
            run_daily_batch_preparation(data_dir=self.data_dir, days=0)
            logger.info("[Job] 오후 부분 배치 작업 성공적으로 완료")
        except Exception as e:
            logger.error("[Job] 오후 배치 실패: %s", e)

    def _auto_trade_cycle(self):
        try:
            result = auto_trade_service.run_enabled_users_cycle()
            if result.get("message") == "no_enabled_users":
                logger.debug("[Job] 자동매매 활성 사용자 없음")
                return
            logger.info("[Job] 자동매매 주기 실행 완료: %s", result)
        except Exception as e:
            logger.error("[Job] 자동매매 주기 실행 실패: %s", e)

    def _strategy_monitor_cycle(self):
        try:
            result = process_saved_strategies()
            if result.get("message") == "no_strategy_files":
                logger.debug("[Job] 모니터링할 전략 파일 없음")
                return

            has_activity = any(item.get("changed") or item.get("processed") for item in result.get("results", []))
            if has_activity:
                logger.info("[Job] 전략 모니터링 실행 완료: %s", result)
        except Exception as e:
            logger.error("[Job] 전략 모니터링 실행 실패: %s", e)

    def shutdown(self):
        self.scheduler.shutdown()
        logger.info("BatchScheduler 종료")
