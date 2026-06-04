# LEVEL_SCANNER_FOUNDATION_V1 Validation Report

Date: 2026-06-04
Scope: `research_lab/level_scanner.py` only. No live-path modules, settings files, or dependency manifests were modified.

## TL;DR

`level_scanner` emits deterministic level facts with the 26-column schema required by the milestone. Focused tests pass, compile validation passes, and a 6-month BTCUSDT smoke run produced 9,230 levels with zero duplicate `level_id` values. Off-the-shelf SMC validation was run for session windows and previous high/low boundary behavior through a local source checkout, without installing the package into the project. The main known divergence is intentional: this scanner uses UTC `[start,end)` session intervals, while `smartmoneyconcepts.sessions()` treats the end timestamp as inclusive.

## Commands Run

```text
.\.venv\Scripts\python.exe -m pytest -o addopts= research_lab\tests\test_level_scanner.py -q
.\.venv\Scripts\python.exe -m compileall research_lab\level_scanner.py research_lab\tests\test_level_scanner.py
```

Result:

```text
9 passed
compileall exit code 0
```

The repository-level pytest config currently references coverage options unavailable in the local venv, so the focused test command overrides `addopts`. No project dependency was added to fix that.

## Output Schema

The scanner returns exactly these 26 parquet-friendly columns:

```text
level_id, symbol, timeframe, category, side, price, top, bottom, formed_at,
available_at, expired_at, swept_at, source, lookback_bars, tolerance_abs,
tolerance_atr, quality_score, is_hpz, metadata_json, session_tag, period_tag,
anchor_type, anchor_timestamp, active_from, active_until, scanner_version
```

`level_id` remains SHA256-based and deterministic. The public helper preserves the milestone formula:

```text
SHA256(f'{source}|{category}|{symbol}|{timeframe}|{price:.8f}|{formed_at.isoformat()}')[:16]
```

Internal records pass a stable category discriminator into that formula to prevent collisions for semantically different rows that share the same broad category, price, and formation timestamp. Example collision classes observed in real data: `PDH` and `PWH` at the same price, or a candle that is both a confirmed swing high and confirmed swing low. The output `category` remains the broad category required by the spec.

## Category Coverage

Implemented categories:

| Category | Status | Notes |
|---|---|---|
| Session extremes | Implemented | UTC-only sessions, `[start,end)` intervals, `session_tag` populated. |
| PDH/PDL/PWH/PWL | Implemented | Daily and weekly previous-period facts, available from the next UTC boundary. |
| EQH/EQL clusters | Implemented | Confirmed pivots, ATR tolerance, `swept_at`, quality score, `is_hpz`. |
| Anchored VWAP | Implemented | Anchored from confirmed swing HH/LL, volume-weighted when volume exists. |
| Round numbers | Implemented | Static 1k/5k/10k-style levels from configured intervals. |
| Liquidation clusters | Stub | Explicit empty DataFrame until Tardis backfill exists. |

The scanner does not construct signal candidates, risk decisions, executable signals, or confluence scores.

## Synthetic Unit Coverage

`research_lab/tests/test_level_scanner.py` covers:

- fixed 26-column output schema
- deterministic 16-character SHA256 hash helper
- UTC session boundary behavior with start inclusive and end exclusive
- previous-day levels available from next UTC day
- equal-cluster confirmed pivots and `swept_at`
- static round-number bounds
- liquidation placeholder empty-schema behavior
- timestamp-column ingestion and UTC normalization
- no imports of trading decision model names

## 6-Month BTCUSDT Smoke Run

Dataset:

```text
research_lab/snapshots/btc_5m_2022_2026.db
symbol: BTCUSDT
source timeframe: 5m
validation window: 2025-06-01T00:00:00Z to 2025-12-01T00:00:00Z
scanner timeframe: 15m resample
```

Result:

| Metric | Value |
|---|---:|
| Source 5m rows | 52,704 |
| Resampled 15m rows | 17,568 |
| Total emitted levels | 9,230 |
| Duplicate `level_id` count | 0 |

Category counts:

| Category | Count |
|---|---:|
| anchored_vwap | 5,028 |
| equal_cluster | 2,633 |
| session_extreme | 1,098 |
| previous_period | 416 |
| round_number | 55 |

Session extreme counts for Asia/London/New York were symmetric over the 183-day sample:

| Session tag | Count |
|---|---:|
| asia_high | 183 |
| asia_low | 183 |
| london_high | 183 |
| london_low | 183 |
| new_york_high | 183 |
| new_york_low | 183 |

## SMC Cross-Validation

Reference source:

```text
%TEMP%\btc_bot_research_sources\smart-money-concepts\smart-money-concepts-master
```

No package was installed and no requirement file was changed. The source checkout was imported through `PYTHONPATH` with `PYTHONIOENCODING=utf-8`, because the package prints a Unicode banner at import time.

### Sessions

Comparison sample: BTCUSDT 15m bars, 2025-06-01 through 2025-06-03.

`smartmoneyconcepts.sessions()` treats end timestamps as inclusive. This scanner treats sessions as `[start,end)`, which avoids double assignment of boundary bars in adjacent windows. After excluding the exact end-boundary bars from SMC output, active bar counts match expected local counts:

| Session | SMC inclusive bars | SMC after end exclusion | Expected local bars |
|---|---:|---:|---:|
| Asia 00:00-08:00 | 99 | 96 | 96 |
| London 07:00-16:00 | 111 | 108 | 108 |
| New York 13:00-22:00 | 111 | 108 | 108 |

Verdict: session boundaries are intentionally different at the end candle only. Local `[start,end)` behavior is preferred for deterministic bucket assignment.

### Previous High/Low

Comparison sample: BTCUSDT 15m bars, 2025-06-01 through 2025-06-03.

SMC first valid `previous_high_low(1D)` output:

| Field | Value |
|---|---:|
| first valid position | 97 |
| first valid previous high | 105,823.6 |
| first valid previous low | 103,704.1 |

Local scanner for the same period:

| Period tag | Price | Formed at | Available at |
|---|---:|---|---|
| PDH | 105,823.6 | 2025-06-01 23:45 UTC | 2025-06-02 00:00 UTC |
| PDL | 103,704.1 | 2025-06-01 23:45 UTC | 2025-06-02 00:00 UTC |

Verdict: values match, but boundary availability differs. SMC reports the first valid previous-period value after the next candle has started; this scanner emits the level fact exactly at the UTC period boundary. The local behavior is better aligned with event replay because the previous day is fully known at 00:00 UTC.

### Liquidity / EQH-EQL

Full SMC `liquidity()` comparison is deferred. The algorithms intentionally differ:

- SMC tolerance is based on a percentage of the full sample high-low range.
- Local scanner tolerance is ATR-local and available-time aware.
- Local scanner emits facts with `formed_at`, `available_at`, and `swept_at`; SMC returns per-row indicator arrays.

This is not a blocker for M1 because the scanner's goal is an auditable local level factory, not one-for-one reproduction of a trading indicator package. A future validation pass should compare cluster prices with tolerance buckets, not exact row equality.

## Known Limitations

- Weekly levels use a UTC Monday-anchored weekly resample. If the operator wants exchange-calendar weeks or Sunday-open crypto weeks, this must be decided before using PWH/PWL for research conclusions.
- Session definitions are fixed UTC windows. No DST or exchange-holiday logic is applied by design.
- Anchored VWAP currently emits one terminal VWAP per confirmed swing anchor over the available window. It is a level-fact baseline, not a full per-bar AVWAP curve.
- Liquidation clusters are an explicit empty placeholder until Tardis backfill ships.
- The SMC comparison was run from a temporary source checkout, not a pinned vendored reference. For audit-grade reproduction, store the exact source archive checksum in `research_lab/external_refs/` in a separate research milestone.

## Verdict

The foundation implementation is ready for Claude Code audit as a research-lab component. It satisfies the core M1 requirements for deterministic level facts, schema stability, category coverage, and local validation. The main audit question is whether the accepted `[start,end)` and 00:00 UTC previous-period availability conventions should be treated as final project contracts or documented as configurable defaults.
