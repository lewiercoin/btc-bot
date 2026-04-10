# SIGNAL_ANALYSIS_V1 — Decision Report

Milestone: SIGNAL-ANALYSIS-V1
Status: EXECUTED — D2 run complete, D3 skipped (condition not met), decision tree resolved
Builder: Cascade
Execution date: 2026-04-10

---

## Purpose

This document answers two questions that block Run #5:
1. Does the sweep+reclaim signal have stationary, cross-regime edge?
2. Which parameters will Optuna exploit as the next volume lever?

Results from:
- `research_lab/runs/event_study_v1.json` (D2 — 145,921 bars, 11,841 events)
- `research_lab/runs/regime_decomposition_v1.json` (D3 — SKIPPED)

D4 states facts and triggers the decision tree.
D4 does NOT make the strategic recommendation — that is Claude Code's role.

---

## D2 Results — Raw Event Study (P1 + MATURE bucket, bar+4 forward return)

Configuration: sweep_proximity_atr=0.4, level_min_age_bars=5, min_hits=3,
equal_level_lookback=50, equal_level_tol_atr=0.25, wick_min_atr=0.3, min_sweep_depth_pct=0.0
Fixed exit: SL=1.0×ATR, TP=2.0×ATR, max_hold=16 bars

NOTE: All 11,841 events fall into P1_MATURE by construction — the feature engine
config filters to proximity_atr <= 0.4 (P1) and level_age_bars >= 5 + hit_count >= 3
(MATURE). All other proximity/structure buckets contain 0 events.

| Segment | n_events | mean_fwd4 | median_fwd4 | p_value | hit_rate | Edge? |
|---|---|---|---|---|---|---|
| S1 (2022-01-01–2022-06-30, bear collapse) | 1,596 | **-0.008** | +0.010 | 0.836 | 28.0% | NO |
| S2 (2022-07-01–2023-03-31, bear range) | 2,196 | **-0.063** | -0.005 | 0.075 | 25.1% | NO (negative mean) |
| S3 (2023-04-01–2024-01-31, recovery/pre-ETF) | 2,373 | **-0.068** | -0.035 | **0.022** | 26.4% | NO (sig. negative) |
| S4 (2024-02-01–2024-09-30, ETF/halving) | 1,859 | **-0.057** | -0.036 | 0.115 | 28.6% | NO (negative mean) |
| S5 (2024-10-01–2025-06-30, rally to ATH) | 2,091 | **-0.084** | -0.019 | **0.012** | 27.4% | NO (sig. negative) |
| S6 (2025-07-01–2026-03-01, recent regime) | 1,726 | **-0.050** | -0.077 | 0.232 | 27.3% | NO (negative mean) |

Threshold for "edge in segment": mean_forward_return (bar+4) > 0 AND p_value < 0.10 AND n_events >= 30

**P1+MATURE edge count: 0 / 6**

Key observations:
- **All 6 segments show negative mean forward returns** at bar+4
- Two segments (S3 recovery, S5 rally) are **statistically significantly negative** (p=0.022, p=0.012)
- Hit rates are uniformly 25–29% — well below the 33.3% breakeven for the 1:2 SL/TP ratio
- S1 (bear collapse) is the only segment near zero (-0.008), but with p=0.836 (no significance)
- The signal has consistent **negative edge** across all market regimes with default parameters

---

## D3 Results — Regime Decomposition (baseline-v3-trial-00195)

D3 condition: mean_fwd4 > 0 AND p < 0.05 in >= 3 SUFFICIENT P1+MATURE segments

**D3 status: SKIPPED — 0/3 required segments qualify (qualifying: [])**

No segment showed positive mean forward return at p < 0.05. The D3 condition gate
was checked automatically; zero segments qualified. The D3 table is not applicable.

---

## Decision Tree

| D2 Result | D3 Result | Conclusion | Action |
|---|---|---|---|
| P1+MATURE edge in ≥4/6 | Edge in ≥4/6 | Signal exists, search problem | Freeze volume levers (D1), reduce to ~20 params, 500+ trials |
| P1+MATURE edge in ≥4/6 | Edge in ≤2/6 | Signal exists, filter problem | Redesign filter stack |
| P1+MATURE edge in 2–3 | — | Seasonal/regime-specific edge | Regime-conditional parameters |
| **P1+MATURE edge in ≤1** | **—** | **No signal at this granularity** | **Stop optimization, redesign feature level** |

**Active branch: P1+MATURE edge in 0/6 → No signal at this granularity → Stop optimization, redesign feature level**

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

### OPEN: Signal Redesign Required

The sweep+reclaim signal with default parameters shows no positive edge in any of 6
regime segments over 4+ years of data. The raw signal generates 11,841 events with
uniformly negative forward returns and hit rates below breakeven. This finding is
independent of the volume lever problem — even with non-inflated parameters, the
signal itself does not demonstrate stationary edge. Any optimization campaign run on
this signal will find apparent edge only through overfitting to noise or exploiting
volume levers.

---

## Reproduction

```bash
python -m research_lab.diagnostics.event_study_v1 --db-path storage/btc_bot.db
python -m research_lab.diagnostics.regime_decomposition_v1  # auto-skips if D2 gate not met
```

Full raw data: `research_lab/runs/event_study_v1.json` (260K lines, 11,841 event records)
