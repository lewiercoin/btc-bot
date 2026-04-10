# SIGNAL_ANALYSIS_V1 — Decision Report

Milestone: SIGNAL-ANALYSIS-V1
Status: PENDING EXECUTION — scripts must be run against production DB to populate results
Builder: Cascade

---

## Purpose

This document answers two questions that block Run #5:
1. Does the sweep+reclaim signal have stationary, cross-regime edge?
2. Which parameters will Optuna exploit as the next volume lever?

It is populated by running:
- `python -m research_lab.diagnostics.event_study_v1` (D2)
- `python -m research_lab.diagnostics.regime_decomposition_v1` (D3, conditional)

Results are in:
- `research_lab/runs/event_study_v1.json`
- `research_lab/runs/regime_decomposition_v1.json` (if D3 condition met)

D4 states facts and triggers the decision tree.
D4 does NOT make the strategic recommendation — that is Claude Code's role.

---

## D2 Results — Raw Event Study (P1 + MATURE bucket, bar+4 forward return)

| Segment | n_events | mean_fwd4 | p_value | hit_rate | Edge? |
|---|---|---|---|---|---|
| S1 (2022-01-01–2022-06-30, bear collapse) | [PENDING] | [PENDING] | [PENDING] | [PENDING] | [PENDING] |
| S2 (2022-07-01–2023-03-31, bear range) | [PENDING] | [PENDING] | [PENDING] | [PENDING] | [PENDING] |
| S3 (2023-04-01–2024-01-31, recovery/pre-ETF) | [PENDING] | [PENDING] | [PENDING] | [PENDING] | [PENDING] |
| S4 (2024-02-01–2024-09-30, ETF/halving) | [PENDING] | [PENDING] | [PENDING] | [PENDING] | [PENDING] |
| S5 (2024-10-01–2025-06-30, rally to ATH) | [PENDING] | [PENDING] | [PENDING] | [PENDING] | [PENDING] |
| S6 (2025-07-01–2026-03-01, recent regime) | [PENDING] | [PENDING] | [PENDING] | [PENDING] | [PENDING] |

Threshold for "edge in segment": mean_forward_return (bar+4) > 0 AND p_value < 0.10 AND n_events >= 30

**P1+MATURE edge count: [PENDING] / 6**

---

## D3 Results — Regime Decomposition (baseline-v3-trial-00195)

D3 condition: mean_fwd4 > 0 AND p < 0.05 in >= 3 SUFFICIENT P1+MATURE segments

D3 status: [PENDING — depends on D2 results]

| Segment | trade_count | expectancy_r | profit_factor | win_rate | max_drawdown_pct |
|---|---|---|---|---|---|
| S1 (bear collapse) | [PENDING] | [PENDING] | [PENDING] | [PENDING] | [PENDING] |
| S2 (bear range) | [PENDING] | [PENDING] | [PENDING] | [PENDING] | [PENDING] |
| S3 (recovery/pre-ETF) | [PENDING] | [PENDING] | [PENDING] | [PENDING] | [PENDING] |
| S4 (ETF/halving) | [PENDING] | [PENDING] | [PENDING] | [PENDING] | [PENDING] |
| S5 (rally to ATH) | [PENDING] | [PENDING] | [PENDING] | [PENDING] | [PENDING] |
| S6 (recent regime) | [PENDING] | [PENDING] | [PENDING] | [PENDING] | [PENDING] |

---

## Decision Tree

| D2 Result | D3 Result | Conclusion | Action |
|---|---|---|---|
| P1+MATURE edge in ≥4/6 | Edge in ≥4/6 | Signal exists, search problem | Freeze volume levers (D1), reduce to ~20 params, 500+ trials |
| P1+MATURE edge in ≥4/6 | Edge in ≤2/6 | Signal exists, filter problem | Redesign filter stack |
| P1+MATURE edge in 2–3 | — | Seasonal/regime-specific edge | Regime-conditional parameters |
| P1+MATURE edge in ≤1 | — | No signal at this granularity | Stop optimization, redesign feature level |

**Active branch: [PENDING — populate after running D2/D3]**

---

## D1 Summary — Volume Lever Audit

26 of ~45 ACTIVE parameters are volume levers. Full table: `docs/diagnostics/VOLUME_LEVER_AUDIT.md`

Confirmed minimum set (from handoff):
- Signal generation: sweep_proximity_atr, level_min_age_bars, min_hits, equal_level_lookback, equal_level_tol_atr, wick_min_atr, min_sweep_depth_pct
- Filter: confluence_min, direction_tfi_threshold, all active weight_* params
- Execution: max_trades_per_day, max_open_positions, max_consecutive_losses, cooldown_minutes_after_loss

Additional levers identified: sweep_buf_atr, reclaim_buf_atr, tfi_impulse_threshold, post_liq_tfi_abs_min, allow_long_in_uptrend, min_rr, daily_dd_limit, weekly_dd_limit

---

## Open Items

### OPEN: Objective Function Vulnerability

OPEN: Optuna multi-objective does not penalize volume inflation. A configuration with
800 trades at PF 1.01 can dominate 200 trades at PF 1.15 on the drawdown axis.
Structural fix required before Run #5: either minimum selectivity constraint or
trade-quality objective. Separate milestone.

---

## How to Populate This Document

1. Ensure production DB is available at `storage/btc_bot.db`
2. Run: `python -m research_lab.diagnostics.event_study_v1`
3. Copy P1+MATURE stats from console output or `research_lab/runs/event_study_v1.json`
   into the D2 Results table above
4. Determine D2 edge count and check D3 condition:
   - If edge_count >= 3 (p < 0.05): run `python -m research_lab.diagnostics.regime_decomposition_v1`
   - If edge_count < 3: skip D3, note reason in D3 status field
5. Fill D3 table if applicable
6. Determine active branch from decision tree
7. Replace all `[PENDING]` with actual values
8. Update "Active branch" line with the triggered branch
9. Hand off to Claude Code for strategic recommendation
