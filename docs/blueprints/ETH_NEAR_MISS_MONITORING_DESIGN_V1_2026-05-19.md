# ETH Near-Miss Monitoring Design V1

**Milestone:** `ETH_NEAR_MISS_MONITORING_DESIGN_V1`  
**Status:** `READY_FOR_AUDIT_DESIGN_ONLY`  
**Scope:** Design only. No runtime implementation, PAPER deployment, LIVE deployment, or code-path change.  
**Decision date:** 2026-05-19  
**Asset:** `ETHUSDT` Binance USDT perpetual futures  
**Strategy:** Frozen trial-00095 sweep/reclaim transfer, no ETH-specific parameter tuning

## Executive Decision

ETH trial-00095 transfer evidence is strong enough to prepare a shadow
monitoring contract, but not strong enough to deploy ETH to PAPER without a
runtime observation phase.

This design defines how ETH near-miss and shadow-signal monitoring should work
after the M4 BTC checkpoint if the user chooses to continue toward multi-asset
runtime integration.

This document does not approve ETH trading.

## Internal Consultation Summary

The safe path is:

1. Keep BTC PAPER and BTC M4 monitoring unchanged through 2026-06-13.
2. Treat BTC M4 as a BTC baseline stability gate before any multi-asset runtime
   change.
3. Treat ETH transfer research as decision-grade offline evidence, not runtime
   approval.
4. Before ETH can place PAPER orders, run ETH in shadow/no-order mode with
   symbol-local near-miss diagnostics.
5. Keep ETH monitoring independent from BTC M4 so BTC threshold decisions are
   not contaminated by ETH behavior.

## Non-Goals

This milestone explicitly does not:

- implement ETH shadow runtime;
- modify `core/**`, `execution/**`, `orchestrator.py`, `main.py`,
  `settings.py`, `storage/**`, or `backtest/**`;
- deploy ETH to PAPER or LIVE;
- change BTC M4 monitoring;
- change BTC trial-00095 parameters;
- tune ETH-specific parameters;
- lower ETH or BTC sweep thresholds;
- add SOL or any other asset;
- approve multi-asset runtime integration.

## Why ETH Needs Its Own Monitoring

BTC M4 answers a BTC-specific question:

> Are current BTC sweep depths clustering just below the active
> `min_sweep_depth_pct = 0.00649` threshold?

ETH has separate volatility, liquidity, wick geometry, OI behavior, and funding
microstructure. The audited ETH transfer replay shows that frozen trial-00095
works offline, but it does not prove that live ETH sweep-depth distribution will
match BTC or that ETH signal frequency will behave like the historical replay.

ETH therefore needs its own shadow evidence before PAPER orders are allowed.

## Required Deployment Sequence

ETH monitoring may only start after these gates:

1. BTC M4 checkpoint completed and audited.
2. User approves continuing the multi-asset path.
3. Multi-asset runtime implementation is built and audited with ETH in
   `shadow_no_orders` mode.
4. BTC PAPER behavior remains unchanged during initial ETH shadow collection.

ETH PAPER orders remain blocked until the ETH shadow checkpoint passes audit.

## Shadow Mode Contract

Future runtime should support three symbol states:

| State | Behavior |
|---|---|
| `disabled` | No data collection, no signals, no diagnostics. |
| `shadow_no_orders` | Build ETH snapshots, features, regime, signal diagnostics, governance/risk diagnostics, near-miss payloads; never open positions. |
| `paper_enabled` | ETH may place PAPER orders only after separate audit and user approval. |

The first ETH runtime milestone must use `shadow_no_orders`.

## ETH Diagnostic Payload Contract

Every ETH decision cycle in shadow mode should persist a symbol-explicit
decision outcome with:

- `symbol = ETHUSDT`
- `timestamp_utc`
- `config_hash`
- `strategy_profile = trial_00095_transfer`
- `shadow_mode = true`
- `signal_generated`
- `signal_blocker`
- `sweep_detected`
- `reclaim_detected`
- `sweep_side`
- `sweep_level`
- `sweep_depth_pct`
- `min_sweep_depth_pct`
- `close_vs_reclaim_buffer_atr`
- `wick_vs_min_atr`
- `sweep_vs_buffer_atr`
- `regime`
- `context_session`
- `tfi_60s`
- `oi_zscore_60d`
- `funding_pct_60d`
- `confluence_score_preview`
- `candidate_direction_preview`
- `governance_shadow_decision`
- `portfolio_shadow_decision`
- `portfolio_veto_reason`

If `signal_blocker = sweep_too_shallow` and `sweep_depth_pct` is above the ETH
near-miss floor, include:

```json
{
  "near_miss_diagnostics": {
    "symbol": "ETHUSDT",
    "sweep_depth_pct": 0.0,
    "threshold": 0.00649,
    "depth_gap_pct": 0.0,
    "depth_bucket": "near_miss_low",
    "regime": "uptrend",
    "session_hour": 0,
    "rejection_reasons": []
  }
}
```

The nested `near_miss_diagnostics.sweep_depth_pct` field is mandatory. This
copies the corrected BTC M4 contract and prevents a second parser mismatch.

## ETH Near-Miss Buckets

Use the frozen trial-00095 threshold unless a later audited milestone changes
it:

| Bucket | Condition | Meaning |
|---|---|---|
| `far_below` | `depth < 0.00400` | Too shallow for threshold discussion. |
| `near_miss_low` | `0.00400 <= depth < 0.00519` | Below 80% of baseline threshold. |
| `near_miss_mid` | `0.00519 <= depth < 0.00584` | Within 20% of baseline threshold. |
| `near_miss_high` | `0.00584 <= depth < 0.00649` | Within 10% of baseline threshold. |
| `baseline_pass` | `depth >= 0.00649` | Passes frozen trial-00095 sweep depth. |

The floor `0.00400` is diagnostic only. It is not an alternate trading
threshold.

## Shadow Checkpoints

### Day 3 Operational Check

Purpose: catch payload, parser, process, and data issues early.

Required checks:

- exactly one BTC PAPER runtime process;
- ETH shadow mode does not open positions;
- no ETH orders in paper/live tables;
- ETH decision outcomes have `symbol = ETHUSDT`;
- nested `near_miss_diagnostics.sweep_depth_pct` present for near-misses;
- BTC M4 rows remain symbol-separated and unchanged;
- no duplicate active config hashes for the same symbol.

Day 3 cannot approve ETH PAPER.

### Day 14 Shadow Check

Purpose: evaluate whether ETH signal and near-miss behavior resembles the
offline transfer evidence enough to continue.

Required metrics:

- decision cycles;
- generated shadow signals;
- `sweep_too_shallow` count and share;
- near-miss records by bucket;
- max, median, and p90 `sweep_depth_pct`;
- governance shadow pass/veto counts;
- portfolio shadow pass/veto counts;
- same-bar overlap with BTC PAPER signals;
- simulated approved ETH signal count before order placement;
- missing-data or stale-feature count.

Day 14 can only approve continuing shadow collection or scheduling a longer
checkpoint.

### Day 30 Shadow Check

Purpose: decide whether ETH can move from `shadow_no_orders` to ETH PAPER.

Required gates:

| Gate | Requirement |
|---|---|
| Runtime safety | 0 ETH orders while in shadow mode. |
| Payload integrity | 100% of near-miss records have nested depth. |
| Data freshness | No persistent stale ETH features across decision cycles. |
| Process integrity | Single runtime instance; no duplicate symbol workers. |
| Signal availability | At least 10 ETH shadow signals or a documented low-frequency explanation. |
| Near-miss clarity | Threshold-proximate near-misses are quantified; no undocumented threshold change. |
| Portfolio safety | ETH shadow approvals do not breach portfolio caps. |
| BTC isolation | BTC M4/PAPER metrics are unaffected by ETH shadow collection. |

If these gates pass, the next milestone may request ETH PAPER approval. If they
fail, ETH remains shadow-only or the multi-asset path is deferred.

## Threshold Decision Rules

ETH shadow monitoring may not directly change `min_sweep_depth_pct`.

If ETH shows many `near_miss_high` records but few baseline passes, create a
separate offline milestone:

`ETH_SWEEP_DEPTH_THRESHOLD_STABILITY_V1`

That milestone must:

- replay ETH with ceteris-paribus threshold variants;
- preserve frozen non-depth trial-00095 parameters;
- use chronological walk-forward gates;
- compare against the frozen ETH transfer baseline;
- require Claude Code audit before any runtime setting changes.

If ETH shadow shows shallow sweeps far below threshold, do not lower the
threshold. Treat it as no actionable threshold evidence.

## Separation From BTC M4

BTC M4 and ETH shadow monitoring must remain separate:

- separate symbol field in every decision outcome;
- separate reports;
- separate config hashes by symbol/profile;
- separate near-miss bucket counts;
- separate threshold recommendations;
- no aggregation of BTC and ETH near-misses into one threshold conclusion.

BTC M4 can recommend a BTC action only. ETH shadow can recommend an ETH action
only.

## Audit Questions

Claude Code should verify:

1. Does this design preserve design-only scope and avoid runtime approval?
2. Does it correctly keep BTC M4 as a blocker for multi-asset runtime changes?
3. Does it define an ETH-specific near-miss payload compatible with the fixed
   BTC M4 contract?
4. Are ETH threshold decisions blocked behind a separate offline stability
   milestone?
5. Are Day 3, Day 14, and Day 30 checkpoints concrete and auditable?
6. Does the design prevent ETH shadow from contaminating BTC M4 conclusions?
7. Does it avoid ETH PAPER approval without a later shadow checkpoint audit?

## Builder Verdict

`READY_FOR_AUDIT_DESIGN_ONLY`

ETH can proceed toward a future shadow/no-order monitoring implementation after
the BTC M4 checkpoint, but this design does not authorize runtime changes or
ETH PAPER trading.
