# MARKET TRUTH LAYER V3 - AUDIT & DESIGN

**Auditor:** Claude Code  
**Date:** 2026-04-21  
**Purpose:** Independent verification system for market data → features → decisions  
**Status:** IN PROGRESS

---

## PART 1 — CURRENT SYSTEM AUDIT

### 1.1 Market Data Sources

**REST API (Primary)** - [BinanceFuturesRestClient](c:\development\btc-bot\data\rest_client.py)

| Data Type | Endpoint | Fields | Frequency | Persisted? |
|---|---|---|---|---|
| **OHLCV Candles** | `/fapi/v1/klines` | open, high, low, close, volume, open_time | Per decision cycle (15m intervals) | ❌ NO - only derived CVD |
| **Book Ticker** | `/fapi/v1/ticker/bookTicker` | bid, ask | Per cycle | ❌ NO |
| **Funding History** | `/fapi/v1/fundingRate` | fundingRate, fundingTime | Per cycle (last 200) | ❌ NO |
| **Open Interest** | `/fapi/v1/openInterest` | openInterest, timestamp | Per cycle | ✅ YES → `oi_samples` |
| **Agg Trades** | `/fapi/v1/aggTrades` | qty, price, is_buyer_maker, time | Fallback if WS fails | ❌ NO - only TFI/CVD derived |

**WebSocket (Preferred for flow)** - [BinanceFuturesWebsocketClient](c:\development\btc-bot\data\websocket_client.py)

| Stream | Data | Window | Persisted? |
|---|---|---|---|
| `@aggTrade` | Aggregated trades | 15m rolling buffer | ❌ NO - only TFI/CVD derived |
| `@forceOrder` | Liquidation events | 60s rolling buffer | ❌ NO |

**External (DB-stored)** - [MarketDataAssembler._load_external_bias()](c:\development\btc-bot\data\market_data.py#L308)

| Source | Field | Persisted? |
|---|---|---|
| `daily_external_bias` table | `etf_bias_5d`, `dxy_close` | ✅ YES |

---

### 1.2 Snapshot Creation

**Location:** [MarketDataAssembler.build_snapshot()](c:\development\btc-bot\data\market_data.py#L100)  
**Called by:** [BotOrchestrator._build_snapshot()](c:\development\btc-bot\orchestrator.py#L727) at start of each decision cycle

**Timing:**
```python
# orchestrator.py:348
snapshot = self._build_snapshot(timestamp)  # timestamp = decision cycle start time (UTC)
```

**MarketSnapshot Fields:**

| Field | Source | Type | Notes |
|---|---|---|---|
| `symbol` | Config | str | BTCUSDT |
| `timestamp` | Cycle start | datetime | System time (UTC) |
| `price` | REST book ticker | float | **(bid + ask) / 2** - COMPUTED |
| `bid` | REST book ticker | float | Exchange |
| `ask` | REST book ticker | float | Exchange |
| `candles_15m` | REST klines | list[dict] | Last 300 bars |
| `candles_1h` | REST klines | list[dict] | Last 300 bars |
| `candles_4h` | REST klines | list[dict] | Last 300 bars |
| `funding_history` | REST funding | list[dict] | Last 200 samples |
| `open_interest` | REST OI | float | Latest value |
| `aggtrades_bucket_60s` | WS or REST | dict | **TFI/CVD** - DERIVED |
| `aggtrades_bucket_15m` | WS or REST | dict | **TFI/CVD** - DERIVED |
| `force_order_events_60s` | WS only | list[dict] | Liquidations (60s window) |
| `etf_bias_daily` | DB | float \| None | External macro |
| `dxy_daily` | DB | float \| None | External macro |
| `quality` | Metadata | dict | Flow coverage metrics |

**Critical Observations:**

1. **No exchange timestamp captured** - only system `timestamp` (when bot makes request)
2. **No latency measurement** - no `exchange_time - system_time` delta
3. **Raw OHLC NOT persisted** - only aggregated into candles table (but that table is empty in production)
4. **TFI/CVD are DERIVED** - not raw trade data
5. **Snapshot.price is COMPUTED** - midpoint, not last trade price

---

### 1.3 What Is Currently Persisted?

| Table | What's Stored | Completeness | Can Reconstruct Snapshot? |
|---|---|---|---|
| `candles` | OHLCV per timeframe | ❌ **EMPTY IN PRODUCTION** | NO |
| `funding` | Historical funding rates | ❌ **NOT POPULATED** | NO |
| `open_interest` | Legacy OI (deprecated) | ❌ **NOT POPULATED** | NO |
| `oi_samples` | OI + `captured_at` timestamp | ✅ YES | **Partial** - OI only |
| `aggtrade_buckets` | Deprecated | ❌ **NOT POPULATED** | NO |
| `cvd_price_history` | TFI/CVD + snapshot.price | ✅ YES | **Partial** - derived metrics only |
| `force_orders` | Liquidation events | ❌ **NOT USED** | NO |
| `signal_candidates` | Signal + `features_json` | ✅ YES | **Features only, not inputs** |
| `executable_signals` | Approved signals | ✅ YES | Decision layer |
| `decision_outcomes` | Cycle outcomes | ✅ YES | Decision layer |

**Persistence Verdict:**

- **OI samples:** ✅ Captured with `captured_at` (system time when fetched)
- **CVD/TFI/Price:** ✅ Captured with `captured_at`
- **Features:** ✅ Stored as JSON in `signal_candidates.features_json`
- **Raw OHLC:** ❌ **NOT STORED**
- **Bid/Ask:** ❌ **NOT STORED**
- **Funding:** ❌ **NOT STORED**
- **Exchange timestamps:** ❌ **NOT STORED**

---

### 1.4 Timing Analysis

**Decision Cycle Sequence:**

```
1. timestamp = now() (UTC, 15m boundary)                    # orchestrator.py:348
2. snapshot = _build_snapshot(timestamp)                    # orchestrator.py:348
   └─ REST calls to Binance (sequential):
      ├─ fetch_book_ticker()                               # ~50-200ms
      ├─ fetch_klines(15m, 1h, 4h)                         # ~100-300ms each
      ├─ fetch_funding_history()                           # ~50-150ms
      ├─ fetch_open_interest()                             # ~50-100ms
      └─ fetch_agg_trades_window() [if WS unavailable]     # ~200-500ms
3. features = feature_engine.compute(snapshot)              # orchestrator.py:410
4. regime = regime_engine.classify(features)                # orchestrator.py:415
5. signal = signal_engine.generate(features, regime)        # orchestrator.py:417
6. governance.evaluate(signal)                              # orchestrator.py:450
7. risk.evaluate(signal)                                    # orchestrator.py:474
8. execution.execute_signal()                               # orchestrator.py:499
```

**Latency Issues:**

| Risk | Evidence | Impact |
|---|---|---|
| **Stale REST data** | No `exchange_timestamp` vs `system_timestamp` check | Unknown if data is seconds-old |
| **Sequential fetches** | 5+ REST calls, ~500-1500ms total | Snapshot spans 0.5-1.5s window |
| **No lookahead protection** | Candles fetched AFTER cycle start | Could include partial future bar |
| **Clock skew** | No NTP sync verification | System time vs exchange time drift |

**Timing Verdict:** ⚠️ **UNVERIFIED**

- No proof that snapshot data is from the intended 15m boundary
- No latency tracking
- No detection of stale/future-leaking data

---

### 1.5 Can We Reconstruct Snapshot Inputs?

**Question:** For a given `decision_outcomes.cycle_timestamp`, can we recreate the exact `MarketSnapshot` used?

**Answer:** ❌ **NO - CRITICAL DATA MISSING**

| Required Field | Available? | Source |
|---|---|---|
| OHLC candles (15m, 1h, 4h) | ❌ NO | Not persisted |
| Bid/Ask at decision time | ❌ NO | Not persisted |
| Funding history | ❌ NO | Not persisted |
| Open Interest | ✅ PARTIAL | `oi_samples.oi_value` (but no exact match guarantee) |
| TFI/CVD | ✅ YES | `cvd_price_history` |
| Force orders | ❌ NO | Not persisted |
| External bias | ✅ YES | `daily_external_bias` |

**Blocking Issues:**

1. **Candles:** REST `/klines` returns CLOSED bars. If decision cycle runs at `15:00:00`, we don't know if the `14:45` bar was final or still forming.
2. **Bid/Ask:** Snapshot captures `(bid+ask)/2` but we can't verify slippage assumptions without raw bid/ask.
3. **Funding:** Only latest funding matters for regime, but we don't store the exact history the bot saw.

**Reconstruction Verdict:** ❌ **IMPOSSIBLE**

Without raw OHLC, bid/ask, and funding at decision time, we cannot:
- Recompute features independently
- Verify FeatureEngine correctness
- Achieve backtest parity
- Detect data quality issues

---

## PART 2 — MARKET TRUTH LAYER (TARGET SCHEMA)

### 2.1 Proposed Schema: `market_snapshots`

```sql
CREATE TABLE IF NOT EXISTS market_snapshots (
    -- IDENTITY
    snapshot_id TEXT PRIMARY KEY,                    -- UUID
    cycle_timestamp TEXT NOT NULL,                   -- Decision cycle start (UTC, ISO)
    symbol TEXT NOT NULL,                            -- BTCUSDT
    
    -- TIMING & SOURCE
    exchange_server_time TEXT,                       -- Exchange server time (from response header or ticker)
    system_capture_started_at TEXT NOT NULL,        -- When snapshot build started
    system_capture_finished_at TEXT NOT NULL,       -- When snapshot build finished
    latency_ms INTEGER,                              -- Capture duration
    
    -- PRICE SNAPSHOT (PRIMARY)
    bid_price REAL NOT NULL,                         -- REQUIRED
    ask_price REAL NOT NULL,                         -- REQUIRED
    last_price REAL,                                 -- Optional (bookTicker may not have this)
    
    -- OPEN INTEREST
    open_interest REAL NOT NULL,                     -- REQUIRED
    oi_exchange_timestamp TEXT,                      -- Exchange OI timestamp (if available)
    
    -- FUNDING (LATEST)
    funding_rate REAL,                               -- Latest funding rate
    funding_timestamp TEXT,                          -- When this rate was set
    
    -- CANDLE SNAPSHOTS (JSON ARRAYS)
    candles_15m_json TEXT NOT NULL,                  -- Last N bars (full OHLCV)
    candles_1h_json TEXT NOT NULL,
    candles_4h_json TEXT NOT NULL,
    
    -- FLOW METRICS (DERIVED BUT CRITICAL)
    tfi_60s REAL,
    cvd_60s REAL,
    tfi_15m REAL,
    cvd_15m REAL,
    flow_source TEXT,                                -- 'ws' | 'rest'
    flow_coverage_60s REAL,                          -- Ratio of window covered
    flow_coverage_15m REAL,
    
    -- LIQUIDATIONS
    force_orders_60s_json TEXT,                      -- Liquidation events (if any)
    
    -- EXTERNAL BIAS
    etf_bias_daily REAL,
    dxy_daily REAL,
    
    -- DATA QUALITY
    data_quality_flag TEXT NOT NULL DEFAULT 'ok',    -- 'ok' | 'degraded' | 'stale' | 'partial'
    quality_notes_json TEXT,                         -- Detailed quality metadata
    
    -- META
    config_hash TEXT NOT NULL,                       -- Bot config version
    schema_version TEXT NOT NULL DEFAULT 'v1',       -- Snapshot schema version
    
    UNIQUE(cycle_timestamp, symbol)
);

CREATE INDEX IF NOT EXISTS idx_market_snapshots_cycle ON market_snapshots(cycle_timestamp);
CREATE INDEX IF NOT EXISTS idx_market_snapshots_quality ON market_snapshots(data_quality_flag);
```

### 2.2 Field Classification

| Field | Status | Rationale |
|---|---|---|
| `snapshot_id` | **REQUIRED** | Primary key, links to decisions |
| `cycle_timestamp` | **REQUIRED** | Decision cycle identity |
| `bid_price`, `ask_price` | **REQUIRED** | Core market truth |
| `open_interest` | **REQUIRED** | Regime input |
| `candles_*_json` | **REQUIRED** | Feature computation inputs |
| `funding_rate` | **REQUIRED** | Regime classification |
| `tfi_*`, `cvd_*` | **OPTIONAL** | Derived, can recompute |
| `exchange_server_time` | **OPTIONAL** | Nice-to-have for latency analysis |
| `force_orders_60s_json` | **OPTIONAL** | Low signal value currently |
| `etf_bias_daily`, `dxy_daily` | **OPTIONAL** | External, already in separate table |

---

## PART 3 — LAYER BINDING

### 3.1 Link Snapshot → Features → Decision

**New Foreign Keys:**

```sql
-- Link decision outcomes to snapshots
ALTER TABLE decision_outcomes ADD COLUMN snapshot_id TEXT REFERENCES market_snapshots(snapshot_id);

-- Link signal candidates to snapshots (features derive from this)
ALTER TABLE signal_candidates ADD COLUMN snapshot_id TEXT REFERENCES market_snapshots(snapshot_id);
```

**Verification Chain:**

```sql
-- Full audit trail for a given decision
SELECT 
    d.cycle_timestamp,
    d.outcome_group,
    s.snapshot_id,
    s.bid_price,
    s.ask_price,
    s.open_interest,
    s.data_quality_flag,
    c.features_json
FROM decision_outcomes d
LEFT JOIN market_snapshots s ON s.snapshot_id = d.snapshot_id
LEFT JOIN signal_candidates c ON c.signal_id = d.signal_id
WHERE d.cycle_timestamp = ?;
```

---

---

## PART 4 — FEATURE RECOMPUTATION ENGINE

### 4.1 Purpose

**Goal:** Independently recompute features from raw market snapshot data and compare against `FeatureEngine` output to detect:
- Computation errors
- Drift over time
- Data quality degradation
- Implementation bugs

### 4.2 Module: `validation/recompute_features.py`

**Interface:**

```python
@dataclass
class FeatureValidationResult:
    snapshot_id: str
    cycle_timestamp: datetime
    feature_name: str
    original_value: float | None
    recomputed_value: float | None
    abs_diff: float
    rel_diff_pct: float
    status: str  # 'OK' | 'WARNING' | 'CRITICAL' | 'MISSING'
    notes: str

class FeatureRecomputationEngine:
    """
    Independently recomputes features from market_snapshots and compares
    against signal_candidates.features_json for validation.
    """
    
    def validate_snapshot(self, snapshot_id: str) -> list[FeatureValidationResult]:
        """
        For a given snapshot_id:
        1. Load raw market data from market_snapshots
        2. Recompute features using reference implementations
        3. Load original features from signal_candidates.features_json
        4. Compare and report diffs
        """
        pass
    
    def validate_batch(self, cycle_timestamps: list[datetime]) -> pd.DataFrame:
        """Validate multiple cycles, return aggregated drift metrics"""
        pass
```

### 4.3 Recomputable Features

| Feature | Input Requirements | Reference Implementation |
|---|---|---|
| **ATR 15m** | `candles_15m_json` (last 15+ bars) | [compute_atr()](c:\development\btc-bot\core\feature_engine.py#L94) |
| **ATR 4h** | `candles_4h_json` (last 15+ bars) | [compute_atr()](c:\development\btc-bot\core\feature_engine.py#L94) |
| **ATR 4h norm** | ATR 4h / latest close price | Simple division |
| **EMA50 4h** | `candles_4h_json` (last 50+ bars) | [compute_ema()](c:\development\btc-bot\core\feature_engine.py#L82) |
| **EMA200 4h** | `candles_4h_json` (last 200+ bars) | [compute_ema()](c:\development\btc-bot\core\feature_engine.py#L82) |
| **Equal lows/highs** | `candles_15m_json` | [detect_equal_levels()](c:\development\btc-bot\core\feature_engine.py#L110) |
| **Sweep detection** | Latest bar + equal levels + ATR | [detect_sweep_reclaim()](c:\development\btc-bot\core\feature_engine.py#L129) |
| **OI z-score** | `open_interest` + `oi_samples` history | Requires historical OI window |
| **Funding avg/percentile** | `funding_rate` + history | ⚠️ Funding history NOT in snapshot |

**Non-Recomputable Features (require state):**

| Feature | Blocker |
|---|---|
| **TFI/CVD** | Raw aggTrades not stored, only derived buckets |
| **Force order metrics** | Events not stored |
| **Funding percentile** | Funding history not in snapshot |
| **OI baseline** | Requires 60-day rolling window |

### 4.4 Validation Thresholds

| Feature | Acceptable Drift | Warning Threshold | Critical Threshold |
|---|---|---|---|
| ATR 15m | 0% (deterministic) | 0.1% | 1.0% |
| ATR 4h | 0% (deterministic) | 0.1% | 1.0% |
| EMA50 | 0% (deterministic) | 0.05% | 0.5% |
| EMA200 | 0% (deterministic) | 0.05% | 0.5% |
| ATR 4h norm | 0% (deterministic) | 0.1% | 1.0% |
| Equal levels | Match count only | 1 level diff | 2+ levels diff |
| Sweep detection | Boolean match | N/A | Mismatch |

**Rationale:**
- ATR/EMA are pure mathematical functions - ZERO drift expected
- Any drift > 0.1% indicates:
  - Implementation bug
  - Data corruption
  - Floating-point precision issue
  - Different input data (candles mismatch)

---

## PART 5 — DRIFT REPORT

### 5.1 Specification

**Report:** `validation/feature_drift_report.md`

**Inputs:**
- N ≥ 200 most recent decision cycles (with `market_snapshots` populated)
- Corresponding `signal_candidates.features_json`

**Metrics:**

```python
@dataclass
class DriftMetrics:
    feature_name: str
    cycles_analyzed: int
    cycles_with_data: int  # Not all cycles have snapshots
    
    # Absolute error
    mean_abs_error: float
    median_abs_error: float
    max_abs_error: float
    p95_abs_error: float
    
    # Relative error
    mean_rel_error_pct: float
    median_rel_error_pct: float
    max_rel_error_pct: float
    p95_rel_error_pct: float
    
    # Threshold violations
    warning_violations: int
    critical_violations: int
    
    # Verdict
    status: str  # 'OK' | 'WARNING' | 'CRITICAL'
    notes: list[str]
```

### 5.2 Verdict Logic

```python
def assess_drift_status(metrics: DriftMetrics, thresholds: dict) -> str:
    """
    OK: mean < warning_threshold AND critical_violations == 0
    WARNING: mean < critical_threshold OR critical_violations <= 5%
    CRITICAL: mean >= critical_threshold OR critical_violations > 5%
    """
    if metrics.critical_violations > metrics.cycles_with_data * 0.05:
        return 'CRITICAL'
    if metrics.mean_rel_error_pct >= thresholds['critical']:
        return 'CRITICAL'
    if metrics.mean_rel_error_pct >= thresholds['warning']:
        return 'WARNING'
    if metrics.critical_violations > 0:
        return 'WARNING'
    return 'OK'
```

### 5.3 Example Report Format

```markdown
# Feature Drift Report

**Generated:** 2026-04-21T18:00:00Z  
**Cycles Analyzed:** 200  
**Date Range:** 2026-04-14 to 2026-04-21

## Summary

| Feature | Status | Mean Drift | Max Drift | Critical Violations |
|---|---|---|---|---|
| ATR 15m | ✅ OK | 0.00% | 0.02% | 0 |
| ATR 4h | ⚠️ WARNING | 0.08% | 1.2% | 3 |
| EMA50 4h | ✅ OK | 0.00% | 0.01% | 0 |
| EMA200 4h | ❌ CRITICAL | 2.5% | 15.3% | 42 |

## Detailed Findings

### EMA200 4h - CRITICAL DRIFT

**Issue:** Large systematic drift detected starting 2026-04-18.

**Evidence:**
- 42 cycles (21%) exceed 1.0% threshold
- Max drift: 15.3% (cycle 2026-04-18T12:00:00Z)
- Pattern: drift increases with market volatility

**Root Cause Hypothesis:**
1. Candles fetched with different `open_time` alignment
2. Partial/incomplete candle included in calculation
3. Exchange data backfill changed historical bars

**Recommended Action:**
- Investigate candle alignment logic
- Add exchange timestamp validation
- Compare against independent data source
```

---

## PART 6 — TIMING VALIDATION

### 6.1 Snapshot Timing Audit

**Purpose:** Verify that market snapshots represent the intended decision cycle boundary and detect timing anomalies.

**Checks:**

| Check | Method | Pass Criteria |
|---|---|---|
| **Lookahead bias** | Compare candle `open_time` vs `cycle_timestamp` | No candles with `open_time >= cycle_timestamp` |
| **Stale data** | `system_capture_finished_at - exchange_server_time` | Latency < 2000ms |
| **Clock skew** | `system_capture_started_at - cycle_timestamp` | Diff < 100ms |
| **Capture duration** | `latency_ms` distribution | p95 < 1500ms |
| **Data consistency** | Latest candle close time | `cycle_timestamp - 15m <= close_time < cycle_timestamp` |

### 6.2 Timing Report

**Metrics:**

```python
@dataclass
class TimingMetrics:
    cycles_analyzed: int
    
    # Latency
    mean_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    max_latency_ms: float
    
    # Freshness
    stale_data_count: int  # latency > 2000ms
    stale_data_pct: float
    
    # Lookahead
    lookahead_violations: int
    lookahead_examples: list[dict]
    
    # Clock skew
    mean_clock_skew_ms: float
    max_clock_skew_ms: float
    
    verdict: str  # 'PASS' | 'WARNING' | 'FAIL'
```

**Verdict:**
- **PASS:** stale_data_pct < 5%, lookahead_violations == 0, p95_latency < 1500ms
- **WARNING:** stale_data_pct < 10%, lookahead_violations < 5, p95_latency < 2000ms
- **FAIL:** Otherwise

---

## PART 7 — PAPER FILL SANITY CHECK

### 7.1 Purpose

Verify that the PAPER-FILL-FIX (deployed 2026-04-21) is working correctly in production.

**NOT changing execution code** - this is verification only.

### 7.2 Checks

After next paper position opens (post-deployment):

```sql
-- Check 1: Executions table populated
SELECT COUNT(*) FROM executions WHERE position_id LIKE 'paper-%';
-- Expected: > 0

-- Check 2: Fill price != signal reference
SELECT 
    p.position_id,
    p.entry_price AS fill_price,
    es.entry_price AS signal_ref,
    ABS(p.entry_price - es.entry_price) AS diff,
    ABS(p.entry_price - es.entry_price) / es.entry_price * 100 AS diff_pct
FROM positions p
JOIN executable_signals es ON es.signal_id = p.signal_id
WHERE p.position_id LIKE 'paper-%'
  AND p.opened_at > '2026-04-21T17:57:00'  -- After deployment
ORDER BY p.opened_at DESC LIMIT 1;
-- Expected: diff > 0 (fill != reference)

-- Check 3: Fill price ≈ snapshot close (within reason)
SELECT 
    p.position_id,
    p.entry_price AS fill_price,
    p.opened_at,
    (SELECT close FROM candles 
     WHERE timeframe = '1m' 
       AND datetime(open_time) <= datetime(p.opened_at)
     ORDER BY open_time DESC LIMIT 1) AS market_close_1m
FROM positions p
WHERE p.position_id LIKE 'paper-%'
  AND p.opened_at > '2026-04-21T17:57:00'
ORDER BY p.opened_at DESC LIMIT 1;
-- Expected: |fill_price - market_close_1m| < 100 (sanity, not exact)

-- Check 4: No instant TP (unrealistic fills)
SELECT 
    p.position_id,
    p.opened_at,
    p.take_profit_1,
    p.entry_price,
    (p.take_profit_1 - p.entry_price) / p.entry_price * 100 AS dist_to_tp_pct,
    t.exit_reason,
    t.closed_at,
    CAST((julianday(t.closed_at) - julianday(p.opened_at)) * 86400 AS INTEGER) AS seconds_to_close
FROM positions p
LEFT JOIN trade_log t ON t.position_id = p.position_id
WHERE p.position_id LIKE 'paper-%'
  AND p.opened_at > '2026-04-21T17:57:00'
  AND t.exit_reason = 'take_profit_1'
ORDER BY seconds_to_close ASC LIMIT 10;
-- Expected: No closes within < 60 seconds (would indicate fill at TP level)

-- Check 5: MAE distribution sanity
SELECT 
    AVG(mae) AS avg_mae,
    MIN(mae) AS min_mae,
    MAX(mae) AS max_mae,
    COUNT(CASE WHEN mae = 0 THEN 1 END) AS zero_mae_count,
    COUNT(*) AS total_trades
FROM trade_log
WHERE position_id LIKE 'paper-%'
  AND opened_at > '2026-04-21T17:57:00';
-- Expected: avg_mae > 0, zero_mae_count small (few perfect fills)
```

### 7.3 Verdict

**PASS:** All 5 checks pass  
**FAIL:** Any check fails + evidence provided

---

## PART 8 — ACCEPTANCE CRITERIA

### 8.1 Market Truth Layer V3 is COMPLETE when:

| # | Criterion | Verification Method |
|---|---|---|
| 1 | **Every decision cycle has a linked market snapshot** | `SELECT COUNT(*) FROM decision_outcomes WHERE snapshot_id IS NULL` == 0 |
| 2 | **Snapshots contain raw OHLC** | `market_snapshots.candles_15m_json` is NOT NULL and valid JSON |
| 3 | **Features can be recomputed from snapshots** | Drift report shows < 1% mean error for ATR/EMA |
| 4 | **Drift is below thresholds** | 0 CRITICAL verdicts in drift report for deterministic features |
| 5 | **No systematic timing errors** | Timing report verdict == PASS |
| 6 | **Snapshot → Feature → Decision chain intact** | JOIN query succeeds for all cycles |
| 7 | **Data quality metadata captured** | `market_snapshots.data_quality_flag` populated |
| 8 | **Paper fill fix verified** | Executions table populated, fill != reference price |

### 8.2 Backtest Parity Readiness

**Question:** Can we achieve backtest parity (backtest results match paper bot)?

**Answer after V3:**

| Requirement | Status | Notes |
|---|---|---|
| Raw OHLC available | ✅ YES | `market_snapshots` has full candle history |
| Bid/Ask available | ✅ YES | Stored in snapshot |
| Funding history | ⚠️ PARTIAL | Only latest rate, not full history |
| TFI/CVD recomputable | ❌ NO | Raw aggTrades not stored |
| Feature drift < 1% | ⏳ TBD | Requires drift report |
| Timing verified | ⏳ TBD | Requires timing audit |
| Execution semantics match | ✅ YES | Paper fill fix deployed |

**Remaining Gaps for Full Parity:**

1. **Funding history:** Snapshot stores latest rate, but FeatureEngine uses 60-day percentile. Need to store full `funding_history` JSON or link to separate table.
2. **TFI/CVD:** Currently derived from aggTrades, but raw trades not stored. Either:
   - Store raw aggTrades in snapshot (large), OR
   - Accept TFI/CVD as externally-validated inputs (store but don't recompute)
3. **OI baseline:** Requires 60-day rolling window of `oi_samples` - already available.

---

## SUMMARY & RECOMMENDATIONS

### Critical Findings

| # | Finding | Severity | Impact |
|---|---|---|---|
| 1 | Raw OHLC not persisted | 🔴 CRITICAL | Cannot reconstruct features or verify bot decisions |
| 2 | No exchange timestamps | 🔴 CRITICAL | Cannot detect stale/future-leaking data |
| 3 | Candles table empty in production | 🟠 HIGH | Historical data collection broken |
| 4 | No latency tracking | 🟡 MEDIUM | Timing assumptions unverified |
| 5 | Funding history not in snapshot | 🟡 MEDIUM | Partial feature recomputation gap |

### Immediate Actions Required

**Priority 1 (Blocking):**
1. ✅ Implement `market_snapshots` table schema
2. ✅ Modify `MarketDataAssembler.build_snapshot()` to persist snapshot after creation
3. ✅ Link `decision_outcomes.snapshot_id` and `signal_candidates.snapshot_id`

**Priority 2 (Validation):**
4. ⏳ Build `validation/recompute_features.py` module
5. ⏳ Generate drift report for last 200 cycles (once snapshots accumulate)
6. ⏳ Run timing validation report

**Priority 3 (Parity):**
7. ⏳ Add funding history JSON to snapshot
8. ⏳ Decide TFI/CVD storage strategy (raw trades vs validated derived)
9. ⏳ Document remaining backtest parity gaps

### Estimated Effort

| Task | Complexity | Lines of Code | Risk |
|---|---|---|---|
| Schema migration | Low | ~50 | Low (additive only) |
| Snapshot persistence | Medium | ~100 | Medium (orchestrator change) |
| Feature recomputation engine | Medium | ~300 | Low (read-only validation) |
| Drift report generator | Low | ~200 | Low (analysis only) |
| Timing validation | Low | ~150 | Low (analysis only) |

**Total:** ~800 LOC, 1-2 milestones

### Success Metrics (30 days post-deployment)

- ✅ 100% of decision cycles have `snapshot_id`
- ✅ 0 CRITICAL drift violations for ATR/EMA
- ✅ Timing report verdict == PASS
- ✅ Paper fill fix verified (executions table populated)
- ✅ Can answer: "What exact market data did the bot see at cycle X?"

---

## FINAL VERDICT

**Current State:** ❌ **SYSTEM OPERATES ON UNVERIFIED INPUTS**

**Market Truth V3 Status:** 🔴 **NOT IMPLEMENTED**

**Blocking Issues:**
1. Cannot reconstruct snapshots → Cannot verify features → Cannot prove decisions are based on market truth
2. No timing validation → Unknown if data is stale/future-leaking
3. Candles table empty → Historical data collection infrastructure exists but unused

**Recommendation:**

> **HALT all modeling/backtest work until Market Truth V3 is deployed.**
>
> Every strategy parameter, every backtest result, and every edge measurement is potentially invalid if based on unverified feature computations or corrupted market data.
>
> Implement `market_snapshots` persistence FIRST, accumulate 200+ cycles, validate drift, THEN resume modeling work.

**Next Milestone:** `MARKET-TRUTH-V3-SCHEMA-IMPL`

---

**Audit Complete: 2026-04-21T18:30:00Z**  
**Auditor: Claude Code**

