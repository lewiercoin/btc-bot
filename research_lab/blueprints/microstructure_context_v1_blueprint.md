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

Read-only blueprint target:

- Current `FeatureEngine.compute()` starts at `core/feature_engine.py:281`.
- It computes sweep/reclaim at `core/feature_engine.py:308-317`.
- It sets flow quality defaults at `core/feature_engine.py:319-327`.
- It reads CVD/TFI and force-order data at `core/feature_engine.py:339-356`.
- It returns `Features` at `core/feature_engine.py:358-393`.

Recommended future insertion point:

- Build `MicrostructureContext` after line 319, using existing snapshot bid/ask/book/aggTrades, before return construction.
- Add it either as `Features.microstructure_context: MicrostructureContext | None` or as an audited `features_json["microstructure_context"]` extension only after operator approval.
- V1 must not be consumed by `core/signal_engine.py`.

## Contract: Informational-Only V1

V1 allowed behavior:

- compute values in replay/offline mode;
- persist/log values in feature snapshots or research parquet;
- use values for attribution reports;
- use values to propose V2 hypotheses.

V1 forbidden behavior:

- no confluence score weight;
- no governance veto;
- no risk veto;
- no execution sizing;
- no candidate direction inference;
- no threshold rescue for trial-00095.

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

## Open Questions For Operator

1. Should V1 use 60s windows to align with current `flow_bucket_tf`, or add 10s/3s windows for paper parity?
2. Does the historical source DB preserve bid/ask quantities or only bid/ask prices?
3. Should `MicrostructureContext` live in `core/models.py` eventually, or remain research-only until V2?
4. Should unavailable numeric metrics be `None` in dataclasses and nullable in parquet, or stored as numeric sentinels plus quality flags?
5. Is the first use case trial-00095 accepted-trade attribution, near-miss reconstruction, or both?
6. Should flash-crash dates be stress-held-out from optimization?
