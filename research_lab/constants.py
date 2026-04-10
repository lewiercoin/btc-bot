from __future__ import annotations

SQLITE_SOURCE_TABLES = ("candles", "funding", "open_interest", "aggtrade_buckets", "force_orders", "trade_log")

PARAM_STATUS_ACTIVE = "ACTIVE"
PARAM_STATUS_FROZEN = "FROZEN_AT_DEFAULT"
PARAM_STATUS_DEFERRED = "DEFERRED_TO_V02"
PARAM_STATUS_UNSUPPORTED = "UNSUPPORTED_IN_CURRENT_API"

PROMOTION_BLOCKING_RISKS = frozenset({"walkforward_not_passed", "walkforward_fragile"})

MIN_TRADES_DEFAULT = 30
MAX_TRADES_DEFAULT = 10000
