from datetime import timedelta, timezone

KST = timezone(timedelta(hours=9))
REDIS_STRATEGY_INDEX_PREFIX = "autotrade:strategy:index"
REDIS_STRATEGY_PAYLOAD_PREFIX = "autotrade:strategy:payload"
STRATEGY_CACHE_TTL_SECONDS = 60 * 60 * 24 * 3
DEFAULT_REBUTTAL_SCORE_GAP_THRESHOLD = 10
