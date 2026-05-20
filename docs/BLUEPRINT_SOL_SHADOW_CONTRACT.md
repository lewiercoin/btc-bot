# SOL Shadow Contract Design V1

**Milestone:** `SOL_SHADOW_CONTRACT_DESIGN_V1`  
**Status:** `READY_FOR_AUDIT_DESIGN_ONLY`  
**Scope:** Design only. No runtime implementation, shadow deployment, PAPER deployment, LIVE deployment, or code-path change.  
**Decision date:** 2026-05-20  
**Asset:** `SOLUSDT` Binance USDT perpetual futures  
**Strategy:** Frozen trial-00095 sweep/reclaim transfer  
**Candidate SOL risk cap:** 0.15% equity per trade, research-only

## Executive Decision

SOL has enough audited offline evidence to design a future shadow observation
contract, but not enough evidence to deploy SOL shadow or PAPER from this
document.

The audited chain is:

| Milestone | Verdict | Key Evidence |
|---|---|---|
| `SOL_DATA_FEASIBILITY_V1` | PASS | SOL archive/data sources available. |
| `SOL_HISTORICAL_BACKFILL_PILOT_V1` | PASS | 3-day ingestion mechanics safe. |
| `SOL_HISTORICAL_BACKFILL_DATASET_V1` | PASS | Full 2022-2026 SOL dataset complete. |
| `SOL_TRIAL_00095_TRANSFER_FEASIBILITY_V1` | PASS methodology, HYPOTHESIS_FAILED result | SOL ER 2.141, PF 3.42, but standalone DD gate failed. |
| `SOL_DRAWDOWN_FORENSIC_DIAGNOSTIC_V1` | PASS | DD concentrated in 2022/downtrend/crowded conditions; low BTC/ETH correlation. |
| `SOL_RISK_POLICY_DIAGNOSTIC_V1` | PASS | SOL risk caps 0.15%, 0.20%, 0.25% pass; 0.15% selected by conservative rule. |

This design defines how a future SOL shadow phase should be observed and
governed if the user later approves a separate implementation milestone.

This document does not approve SOL trading.

## Non-Goals

This milestone explicitly does not:

- implement SOL shadow runtime;
- deploy SOL shadow, PAPER, or LIVE;
- modify `core/**`, `execution/**`, `orchestrator.py`, `main.py`,
  `settings.py`, `storage/**`, or `backtest/**`;
- change BTC PAPER behavior;
- change BTC M4 monitoring;
- change BTC, ETH, or SOL trial-00095 entry logic;
- change SOL sweep-depth threshold;
- optimize SOL parameters;
- approve SOL risk cap in production settings;
- approve portfolio runtime integration.

## Why SOL Needs A Separate Contract

SOL is not simply ETH with a different symbol.

The offline transfer evidence shows strong SOL expectancy and frequency, but
also a harsher drawdown profile:

- SOL standalone max DD: 32.72R.
- SOL max loss streak: 21.
- Weak regimes: downtrend, crowded leverage, and normal regimes.
- Strong regime: uptrend with ER 2.675 and PF 4.39.
- Daily R correlation with BTC and ETH is low, supporting diversification.

The safe interpretation is:

> SOL may be useful as a third portfolio asset, but only as a smaller,
> separately governed risk sleeve.

## Required Sequence

SOL shadow may only be implemented after these gates:

1. BTC M4 checkpoint completed and audited.
2. User approves continuing multi-asset runtime work.
3. BTC+ETH multi-asset runtime path remains valid or is explicitly revised.
4. SOL shadow implementation milestone is scoped separately and audited.
5. SOL starts in `shadow_no_orders` only.

SOL PAPER remains blocked until a future SOL shadow checkpoint passes audit and
the user explicitly approves PAPER.

## Symbol States

Future runtime should support these states per symbol:

| State | Behavior |
|---|---|
| `disabled` | No data collection, no signal generation, no diagnostics. |
| `shadow_no_orders` | Build snapshots, features, regime, signal, governance, risk, and portfolio diagnostics; persist shadow decisions; place zero orders. |
| `paper_enabled` | Symbol may place PAPER orders only after separate audit and user approval. |

SOL must enter the system as `shadow_no_orders`.

## Setup Isolation

SOL must remain setup-isolated:

- `symbol = SOLUSDT`
- `strategy_profile = trial_00095_transfer`
- `setup_family = sweep_reclaim`
- `risk_policy_profile = sol_015_shadow_candidate`
- `shadow_mode = true`

SOL signals must not be aggregated into BTC M4 conclusions or ETH shadow
conclusions.

Every signal, decision, veto, near-miss, and diagnostic row must include
`symbol = SOLUSDT`.

## Candidate Risk Policy

These values are research-derived candidate policy, not runtime approval:

| Symbol | Candidate Risk Per Trade | Status |
|---|---:|---|
| BTCUSDT | 0.35% | Existing BTC PAPER baseline scope. |
| ETHUSDT | 0.35% | Existing offline multi-asset candidate. |
| SOLUSDT | 0.15% | SOL risk-policy diagnostic selected candidate. |

SOL may not inherit BTC/ETH 0.35% risk by default.

The future implementation must treat per-symbol risk as explicit configuration,
not a shared global constant.

## Portfolio Gate Contract

SOL shadow decisions must pass through the same portfolio gate contract used for
offline diagnostics:

1. Per-symbol signal generation runs independently.
2. Per-symbol governance evaluates symbol-local blockers.
3. Portfolio gate evaluates all candidate signals for the decision cycle.
4. Deterministic ordering:
   `timestamp ASC`, then configured symbol rank, then symbol, then signal id.
5. Portfolio vetoes are persisted even in shadow mode.
6. SOL shadow approval does not place an order.

Recommended symbol order for future three-symbol shadow:

```text
BTCUSDT, ETHUSDT, SOLUSDT
```

This order is deterministic only. It is not a claim that BTC has better edge
than ETH or SOL.

## Diagnostic Payload Contract

Every SOL shadow decision cycle should persist:

- `symbol = SOLUSDT`
- `timestamp_utc`
- `config_hash`
- `strategy_profile = trial_00095_transfer`
- `risk_policy_profile = sol_015_shadow_candidate`
- `shadow_mode = true`
- `signal_generated`
- `signal_blocker`
- `sweep_detected`
- `reclaim_detected`
- `sweep_side`
- `sweep_level`
- `sweep_depth_pct`
- `min_sweep_depth_pct`
- `regime`
- `context_session`
- `tfi_60s`
- `oi_zscore_60d`
- `funding_pct_60d`
- `confluence_score_preview`
- `candidate_direction_preview`
- `symbol_governance_shadow_decision`
- `symbol_risk_shadow_decision`
- `portfolio_shadow_decision`
- `portfolio_veto_reason`
- `candidate_risk_pct = 0.0015`
- `portfolio_risk_after_pct`
- `gross_notional_after_pct`
- `directional_notional_after_pct`

If `signal_blocker = sweep_too_shallow` and `sweep_depth_pct` is above the SOL
near-miss floor, include:

```json
{
  "near_miss_diagnostics": {
    "symbol": "SOLUSDT",
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

The nested `near_miss_diagnostics.sweep_depth_pct` field is mandatory.

## SOL Near-Miss Buckets

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

Purpose: prove SOL shadow cannot place orders and payloads are sound.

Required checks:

- BTC PAPER runtime remains single-instance.
- SOL is `shadow_no_orders`.
- zero SOL orders;
- zero SOL positions;
- SOL decision rows include `symbol = SOLUSDT`;
- SOL risk profile is `sol_015_shadow_candidate`;
- nested near-miss depth is present for near-miss rows;
- portfolio shadow decisions persist machine-readable veto reasons;
- BTC M4 rows remain symbol-separated and unaffected.

Day 3 cannot approve SOL PAPER.

### Day 14 Behavior Check

Purpose: compare forward SOL shadow behavior with offline transfer evidence.

Required metrics:

- decision cycles;
- generated SOL shadow signals;
- portfolio-approved SOL shadow signals;
- portfolio-vetoed SOL shadow signals;
- `sweep_too_shallow` count and share;
- near-miss records by bucket;
- max, median, and p90 `sweep_depth_pct`;
- SOL shadow loss-streak simulation;
- SOL shadow risk-at-0.15% capital exposure;
- BTC/ETH/SOL same-bar overlap;
- missing-data or stale-feature count.

Day 14 can only approve continuing shadow or pausing SOL.

### Day 30 Shadow Readiness Check

Purpose: decide whether SOL may request PAPER consideration.

Required gates:

| Gate | Requirement |
|---|---|
| Runtime safety | 0 SOL orders and 0 SOL positions during shadow. |
| Payload integrity | 100% of SOL near-miss rows have nested depth. |
| Risk policy integrity | 100% of SOL approved shadow signals use candidate risk 0.15%. |
| Signal availability | At least 20 SOL shadow signals or documented low-frequency explanation. |
| Portfolio safety | SOL shadow approvals do not breach portfolio caps. |
| Drawdown simulation | Forward SOL shadow simulated DD does not contradict the 0.15% risk policy. |
| Correlation | SOL forward shadow correlation with BTC/ETH remains measured and documented. |
| BTC isolation | BTC PAPER and M4 metrics are unaffected. |

If these gates pass, the next milestone may request SOL PAPER consideration.
If they fail, SOL remains shadow-only or is deferred.

## Promotion Blocks

SOL may not move from shadow to PAPER if any of these occur:

- SOL shadow opens an order or position before approval.
- SOL risk cap differs from approved candidate policy without audit.
- SOL threshold is changed without a separate threshold stability milestone.
- SOL shadow diagnostics are missing symbol labels.
- SOL portfolio veto reasons are not persisted.
- SOL drawdown simulation exceeds policy without explanation.
- BTC M4 or BTC PAPER metrics are contaminated by SOL rows.

## Threshold Decision Rules

SOL shadow monitoring may not directly change `min_sweep_depth_pct`.

If SOL near-miss data suggests a threshold question, open a separate milestone:

```text
SOL_SWEEP_DEPTH_THRESHOLD_STABILITY_V1
```

That milestone must:

- hold non-depth trial-00095 parameters fixed;
- replay SOL with predeclared depth variants;
- include walk-forward validation;
- compare against the frozen SOL transfer baseline;
- pass Claude Code audit before any threshold change is considered.

## Audit Questions

1. Is this document design-only with no runtime/code/config changes?
2. Does it keep SOL separate from BTC M4 and ETH shadow conclusions?
3. Does it preserve frozen trial-00095 entry/threshold logic?
4. Does it encode SOL 0.15% as a candidate risk policy, not runtime approval?
5. Are Day 3, Day 14, and Day 30 gates concrete enough for future audit?
6. Does it block SOL PAPER until shadow evidence, audit, and user approval?
