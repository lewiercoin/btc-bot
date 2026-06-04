# Level Scanner Spec

## TL;DR

`level_scanner` is an offline/research module that converts OHLCV, sessions, and future Tardis/liquidation data into auditable level facts. It is a factory of levels for setup portfolio research. It is not a signal engine and does not decide entries. Every emitted level must include provenance, formation time, availability time, invalidation/sweep status where applicable, and deterministic parameters.

## Interface Contract

```python
def scan_levels(ohlcv_df, config) -> pd.DataFrame:
    ...
```

Inputs:

- `ohlcv_df`: UTC-indexed or timestamp-column OHLCV DataFrame.
- `config`: immutable scanner config with timeframe, session definitions, lookbacks, tolerances, and source metadata.

Output schema, parquet-friendly:

| Column | Type | Description |
| --- | --- | --- |
| `level_id` | string | deterministic hash of source, category, symbol, timeframe, level price, formed_at |
| `symbol` | string | e.g. `BTCUSDT` |
| `timeframe` | string | source timeframe, e.g. `15m` |
| `category` | string | one of categories below |
| `side` | string | `HIGH`, `LOW`, `MID`, `BID_LIQ`, `ASK_LIQ`, `ROUND` |
| `price` | float | level price |
| `top` | float nullable | zone top if zone, else same/null |
| `bottom` | float nullable | zone bottom if zone, else same/null |
| `formed_at` | UTC timestamp | first bar that formed the level |
| `available_at` | UTC timestamp | first bar when the level is knowable |
| `expired_at` | UTC timestamp nullable | expiration/invalidation |
| `swept_at` | UTC timestamp nullable | first deterministic sweep event |
| `source` | string | `joshyattridge`, `pyindicators`, `local`, `tardis_placeholder` |
| `lookback_bars` | int nullable | lookback used |
| `tolerance_abs` | float nullable | absolute tolerance |
| `tolerance_atr` | float nullable | ATR-scaled tolerance |
| `quality_score` | float nullable | 0-100 if applicable |
| `is_hpz` | bool nullable | high-probability-zone style flag, research-only |
| `metadata_json` | string/json | parameters and supporting counts |

## Six Level Categories

### 1. Session Extremes

Mechanics:

- Define UTC session windows: Asia, London, New York, and optional kill zones.
- For each session instance, emit session high and low after the session closes, plus rolling active-session high/low for informational context.
- Use `[start, end)` to avoid boundary double counting.

Source:

- joshyattridge `sessions()` as reference; local implementation required.

Cross-validation:

- Compare active flags/high/low against joshyattridge on fixed UTC data.
- Add DST tests proving we are using UTC-defined crypto sessions, not local clock sessions.

### 2. PDH/PDL/PWH/PWL

Mechanics:

- Resample UTC OHLCV to 1D and 1W.
- For each intraday bar, previous period levels are levels from the immediately completed period.
- Emit broken/swept flags separately from level creation.

Source:

- joshyattridge `previous_high_low()` as reference; local implementation required.

Cross-validation:

- Compare outputs on six months BTC with the library after forcing UTC boundaries.
- Unit-test period rollover, first period unavailable, and week boundary.

### 3. EQH/EQL Clusters

Mechanics:

- Detect swing highs/lows with explicit `confirmed_at`.
- Cluster levels within ATR-scaled or percent tolerance.
- Emit cluster only after minimum hits are available.
- Emit `swept_at` when future high/low crosses cluster boundary.

Source:

- Existing btc-bot equal-level logic in `core/feature_engine.py`.
- joshyattridge `liquidity().Swept` as external cross-check.

Cross-validation:

- Compare local cluster counts and swept indices against joshyattridge with matched tolerance.
- Verify no global future range is used in local tolerance.

### 4. Anchored VWAP From Swing HH/LL

Mechanics:

- When a confirmed swing HH/LL forms, anchor cumulative VWAP at `available_at`.
- Emit active AVWAP as a dynamic level series, not a single static price.
- Store anchor reason, anchor bar, and active range.

Source:

- Local implementation; not directly from joshyattridge/PyIndicators.

Cross-validation:

- Synthetic OHLCV with known cumulative VWAP.
- Independent calculation in notebook/script for six-month sample.

### 5. Round Numbers

Mechanics:

- Emit static levels at configurable intervals: 1k, 5k, 10k for BTC.
- Include nearest-above/nearest-below levels for each bar or a compact static table by price regime.
- Mark formation as config start, not market-derived.

Source:

- Local implementation.

Cross-validation:

- Deterministic formula tests around boundary prices.
- Ensure no overproduction of irrelevant far-away levels.

### 6. Liquidation Clusters

Mechanics:

- Placeholder until Tardis liquidation/force-order backfill is complete.
- Cluster forced liquidation prints by price and time bucket.
- Emit side, notional, count, time decay, and swept/absorbed status.

Source:

- Tardis backfill future module.

Cross-validation:

- Compare raw Tardis liquidation rows to local cluster aggregates.
- Gap report must show missing days/hours explicitly.

## Validation Off-The-Shelf

Plan:

1. Select six months of BTC 15m history with clean UTC timestamps.
2. Run local `level_scanner` and external references where available:
   - joshyattridge: sessions, previous highs/lows, liquidity swept.
   - PyIndicators: optional EQH/EQL or zone references only where package functions expose comparable outputs.
3. Normalize output schemas.
4. Compare:
   - exact session active flags;
   - exact PDH/PDL/PWH/PWL values after boundary normalization;
   - tolerance-based EQH/EQL cluster prices;
   - swept bar availability and no-lookahead timing.
5. Report mismatches with examples, not just aggregate accuracy.

Acceptance:

- Session/previous period levels should match exactly after UTC convention is fixed.
- Liquidity clusters may differ, but differences must be explained by local ATR tolerance vs external global range tolerance.
- Any future-confirmed level must expose `available_at > formed_at` where applicable.

## Integration

`level_scanner` is the level factory for setup portfolio research:

- `reclaim_swing`: existing equal high/low levels.
- `reclaim_session`: session extreme levels.
- `reclaim_rejection`: wick/rejection zone levels.
- `reclaim_breaker`: breaker-zone levels.
- `ote_pullback`: dynamic OTE zone levels.
- Future liquidation setup: liquidation cluster levels.

Layer rule:

- Scanner emits facts.
- Setup modules interpret facts into candidates.
- Governance/risk may veto only after a candidate exists.
- Scanner never places trades or modifies runtime state.

## Non-Deliverable

No code in this milestone. This is a specification for later implementation and audit.
