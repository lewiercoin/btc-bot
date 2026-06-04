# MicrostructureContext V1 Blueprint

## TL;DR

`MicrostructureContext` is a deterministic, replayable, informational-only context object derived from top-of-book and recent trade-flow data. V1 exists to log and audit whether spread, L1 imbalance, trade intensity, signed flow, and VWAP-to-mid deviations explain trial-00095 outcomes or near-miss scarcity. It must not affect `signal_engine.py`, governance, risk, sizing, or execution until a separate promotion gate proves independent value.

## Dataclass Signature

```python
@dataclass(slots=True, frozen=True)
class MicrostructureContext:
    timestamp: datetime
    schema_version: str
    source_window_seconds: int
    l1_imbalance: float | None
    spread_to_mid: float | None
    net_order_flow_qty: float | None
    buy_vwap_to_mid: float | None
    sell_vwap_to_mid: float | None
    traded_volume: float | None
    trade_count: int | None
    trade_price_variance: float | None
    realized_volatility: float | None
    volume_concentration: float | None
    quality: dict[str, FeatureQuality]
```

The brief asks for 10 fields; the signature includes metadata plus the 10 metric fields below.

## Ten Metric Fields

| Field | Type | Formula | Source feed |
| --- | --- | --- | --- |
| `l1_imbalance` | `float | None` | `(bid_qty - ask_qty) / (bid_qty + ask_qty)` | book ticker or L1 depth |
| `spread_to_mid` | `float | None` | `(ask - bid) / ((ask + bid) / 2)` | `MarketSnapshot.bid`, `MarketSnapshot.ask` |
| `net_order_flow_qty` | `float | None` | `sum(sign * qty)` over window | aggTrades |
| `buy_vwap_to_mid` | `float | None` | `buy_vwap / mid - 1` | aggTrades + bid/ask |
| `sell_vwap_to_mid` | `float | None` | `sell_vwap / mid - 1` | aggTrades + bid/ask |
| `traded_volume` | `float | None` | `sum(qty)` | aggTrades |
| `trade_count` | `int | None` | count of trades in window | aggTrades |
| `trade_price_variance` | `float | None` | variance of `log(trade_price / mid)` | aggTrades + bid/ask |
| `realized_volatility` | `float | None` | std of log mid/trade returns in window | mid history or aggTrades |
| `volume_concentration` | `float | None` | `max(buy_qty, sell_qty) / (buy_qty + sell_qty)` | aggTrades |

## Graceful Fallback Design

Principles:

- Never silently fill missing values.
- Emit `None` for unavailable numeric fields.
- Attach `FeatureQuality` per metric family with reason and provenance.
- Preserve deterministic output for the same snapshot and history.

Fallbacks:

- Missing bid/ask price: mark `spread_to_mid`, VWAP-to-mid, and price variance unavailable.
- Missing bid/ask qty: mark `l1_imbalance` unavailable; do not infer from trade flow.
- No trades in window: `traded_volume=0.0`, `trade_count=0`, net flow `0.0`; buy/sell VWAP fields unavailable because denominator is zero.
- Only buy or only sell trades: available side VWAP computed; absent side unavailable.
- Missing orderbook depth beyond L1: no error; V1 only requires top-of-book.
- Gaps in aggTrades window: quality degraded/unavailable based on expected coverage threshold; do not forward-fill.
- Replay without sub-minute data: context object may exist with all metric fields unavailable and a quality reason `microstructure_source_missing`.

## Integration Point

### V1 Integration (Informational-Only, Research Lab)

**V1 implementation (research_lab ONLY):**

Compute `MicrostructureContext` in offline replay scripts:

- Example script: `research_lab/replay_with_microstructure.py`
- Input: OHLCV + aggTrades + book_ticker history
- Output: `research_lab/microstructure_context.parquet` as a separate table.

**V1 FORBIDDEN:**

- Do NOT add a field to the `core/models.py` `Features` dataclass.
- Do NOT modify `core/feature_engine.py`.
- Do NOT store `MicrostructureContext` in `storage/btc_bot.db` `decision_outcomes`.

**V1 ALLOWED:**

- Compute context rows in research_lab replay scripts.
- Store context rows in a separate parquet table.
- Join context rows offline for attribution reports.
- Use attribution results to generate V2 hypotheses, for example `spread_to_mid > X` predicting stop-outs.

**Example V1 attribution pattern:**

```python
# research_lab/attribution_microstructure.py
import pandas as pd

features = pd.read_parquet("research_lab/features_snapshot.parquet")
microstructure = pd.read_parquet("research_lab/microstructure_context.parquet")

merged = features.merge(microstructure, on="timestamp", how="left")

stopped_out = merged[merged["outcome"] == "stop_out"]
print(f"Median spread on stop-outs: {stopped_out['spread_to_mid'].median()}")
```

### V2 Integration (After Promotion Gate Passes)

V2 prerequisites are the promotion gate items below. All must pass before any production dataclass or feature-engine change:

1. DATA-INTEGRITY-V1 complete for required source feeds.
2. Offline implementation has fixed-input deterministic tests.
3. Replay parity proves same values from same source history after restart.
4. At least one RUN shows independent lift over trial-00095 baseline, not just subset filtering.
5. MFE accessibility test proves the feature is known before the tradable move is consumed.
6. Walk-forward/nested validation passes with protocol hash and purge where labels overlap.
7. Claude audit confirms no `signal_engine.py` reclaim leak or hidden ML in runtime.
8. Operator explicitly approves promotion scope.

V2 implementation only after the gate passes:

```python
# core/models.py (V2 ONLY, after promotion)
from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class MicrostructureContext:
    # Schema from this blueprint.
    pass


@dataclass(slots=True, frozen=True)
class Features:
    # Existing fields remain unchanged.
    microstructure_context: MicrostructureContext | None = None
```

```python
# core/feature_engine.py (V2 ONLY, after promotion)
def compute(self, snapshot: MarketSnapshot, ...) -> Features:
    # Existing feature computation remains first.
    microstructure_ctx = self._compute_microstructure_context(snapshot)

    return Features(
        # Existing fields remain unchanged.
        microstructure_context=microstructure_ctx,
    )
```

V2 insertion point: after current `core/feature_engine.py` flow-source computation and before `Features` return construction. This is a future reference only, not V1 scope.

### Current Production Code Reference (Read-Only, Do Not Modify in V1)

- Current `FeatureEngine.compute()` starts at `core/feature_engine.py:281`.
- It computes sweep/reclaim at `core/feature_engine.py:308-317`.
- It sets flow quality defaults at `core/feature_engine.py:319-327`.
- It reads CVD/TFI and force-order data at `core/feature_engine.py:339-356`.
- It returns `Features` at `core/feature_engine.py:358-393`.

## Contract: Informational-Only V1

V1 allowed behavior:

- compute values in replay/offline mode;
- persist/log values in separate research parquet;
- use values for attribution reports;
- use values to propose V2 hypotheses.

V1 forbidden behavior:

- no confluence score weight;
- no governance veto;
- no risk veto;
- no execution sizing;
- no candidate direction inference;
- no threshold rescue for trial-00095.

**V1 storage location:**

- Separate parquet table: `research_lab/microstructure_context.parquet`.
- NOT in the `core/models.py` `Features` dataclass.
- NOT in the `storage/btc_bot.db` `decision_outcomes` table.
- NOT in production feature snapshots.

**V1 data flow:**

```text
OHLCV + aggTrades + book_ticker
  -> research_lab/replay_script.py
  -> research_lab/microstructure_context.parquet
  -> offline join with features for attribution reports
```

Audit rule:

- Every downstream report must state whether the context is informational-only or decision-relevant. V1 is always informational-only.

## Promotion Gate To Decision-Relevant V2

All must pass before decision relevance:

1. DATA-INTEGRITY-V1 complete for required source feeds.
2. Offline implementation has fixed-input deterministic tests.
3. Replay parity proves same values from same source history after restart.
4. At least one RUN shows independent lift over trial-00095 baseline, not just subset filtering.
5. MFE accessibility test proves the feature is known before the tradable move is consumed.
6. Walk-forward/nested validation passes with protocol hash and purge where labels overlap.
7. Claude audit confirms no `signal_engine.py` reclaim leak or hidden ML in runtime.
8. Operator explicitly approves promotion scope.

## Test Plan

Offline tests:

- Unit tests for each formula with fixed synthetic snapshots.
- Missing data tests: no bid/ask qty, no trades, only buy trades, only sell trades, zero mid, crossed/invalid book.
- UTC window tests: exact start/end inclusivity, gap handling, duplicate timestamps.
- Replay determinism: same input rows produce identical context values across two runs.
- Quality flag tests: ready/degraded/unavailable reasons are stable and specific.
- Cross-check tests: compare `net_order_flow`, `traded_volume`, and `trade_count` against existing 60s bucket fields where available.
- Non-consumption test: assert no signal/governance/risk code reads microstructure fields in V1.

**V1 isolation tests (before implementing V2):**

- Assert `MicrostructureContext` does not appear in `core/models.py` imports or fields.
- Assert `core/feature_engine.py` does not contain `microstructure` except comments or explicit V2-only documentation.
- Assert there are no references in `core/signal_engine.py`, `governance/`, or `risk/`.
- Verify parquet write/read round-trip for the separate table:

```python
# Test: V1 storage isolation.
ctx = MicrostructureContext(...)
df = pd.DataFrame([ctx])
df.to_parquet("research_lab/microstructure_context.parquet")
loaded = pd.read_parquet("research_lab/microstructure_context.parquet")
assert loaded.iloc[0].to_dict() == ctx.__dict__
```

## Open Questions For Operator

1. Should V1 use 60s windows to align with current `flow_bucket_tf`, or add 10s/3s windows for paper parity?
2. Does the historical source DB preserve bid/ask quantities or only bid/ask prices?
3. Should `MicrostructureContext` live in `core/models.py` eventually, or remain research-only until V2?
4. Should unavailable numeric metrics be `None` in dataclasses and nullable in parquet, or stored as numeric sentinels plus quality flags?
5. Is the first use case trial-00095 accepted-trade attribution, near-miss reconstruction, or both?
6. Should flash-crash dates be stress-held-out from optimization?
