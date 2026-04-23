# Timing Validation Report

Status date: 2026-04-23
Status type: pre-deployment audit + V3 readiness

## Current production verdict

**CRITICAL for exact proof, before V3 deployment.**

Why:
- production currently records `last_ws_message_at` in `runtime_metrics`,
- but it does not persist per-cycle raw truth with exchange timestamps,
- therefore post-hoc proof of:
  - lookahead absence,
  - stale-data rate,
  - per-cycle latency distribution,
  is not possible for historical cycles.

## V3 timing fields now implemented

Per `market_snapshots` row:
- `cycle_timestamp`
- `exchange_timestamp`
- `latency_ms`
- `source_meta_json`

These fields are sufficient for future timing validation.

## Planned validation metrics after deployment

- avg `latency_ms`
- max `latency_ms`
- `% cycles` where `cycle_timestamp - exchange_timestamp` exceeds stale threshold
- source freshness split:
  - REST components
  - WS components

## Initial thresholds

- `latency_ms <= 1000` ms: OK
- `1000 < latency_ms <= 3000` ms: WARNING
- `latency_ms > 3000` ms: CRITICAL
- `cycle_timestamp - exchange_timestamp > 1 candle boundary`: CRITICAL

## Current operator action

Deploy V3, collect at least 200 cycles, then compute timing metrics from `market_snapshots`.
