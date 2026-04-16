from datetime import timedelta, timezone

KST = timezone(timedelta(hours=9))
REDIS_STRATEGY_INDEX_PREFIX = "autotrade:strategy:index"
REDIS_STRATEGY_PAYLOAD_PREFIX = "autotrade:strategy:payload"
REDIS_BATCH_READY_PREFIX = "autotrade:batch-ready"
REDIS_AUTOTRADE_CONFIG_PREFIX = "autotrade:config"
REDIS_AUTOTRADE_CONFIG_INDEX_KEY = "autotrade:config:index"
REDIS_AUTOTRADE_TICKER_SNAPSHOT_PREFIX = "autotrade:ticker-snapshot"
STRATEGY_CACHE_TTL_SECONDS = 60 * 60 * 24 * 3
DEFAULT_REBUTTAL_SCORE_GAP_THRESHOLD = 10
