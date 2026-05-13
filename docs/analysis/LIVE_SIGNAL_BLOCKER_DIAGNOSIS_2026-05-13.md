# Live Signal Blocker Diagnosis

**Date:** 2026-05-13  
**Author:** Cascade (builder)  
**Diagnostic window:** 2026-05-08 (deployment) → 2026-05-13  
**Status:** COMPLETE  
**Verdict:** WORKING_AS_DESIGNED_BUT_RARE

## Executive Summary

Trial-00095 has been running correctly since deployment on 2026-05-08. The low trade frequency (1 trade in 5 days) is **not caused by governance blocking or a bug**. It is caused by the signal layer's sweep geometry: the Optuna-optimized `min_sweep_depth_pct = 0.00649` (0.649%) correctly rejects the shallow sweeps that current market conditions produce.

**98.9% of decision cycles are rejected at the sweep detection layer**, split between:
- `no_sweep` (41%) — no liquidity sweep detected at all
- `sweep_too_shallow` (58%) — sweep detected but depth below 0.649% threshold

Governance vetoed only 1 of 461 cycles (0.2%). The earlier Cascade consultation incorrectly diagnosed governance as the primary blocker — that was based on pre-deployment signal data (May 1) which used different parameters.

## Production Configuration (Verified)

The runtime overlay (`settings.json`) contains the actual Optuna trial-00095 parameters:

| Parameter | Value | Source |
|---|---|---|
| `min_sweep_depth_pct` | **0.00649** (0.649%) | Optuna trial-00095 via settings.json |
| `confluence_min` | 3.9 | Optuna trial-00095 via settings.json |
| `tfi_impulse_threshold` | 0.31 | Optuna trial-00095 via settings.json |
| `sweep_buf_atr` | 0.46 | Optuna trial-00095 via settings.json |
| `reclaim_buf_atr` | 0.07 | Optuna trial-00095 via settings.json |
| `config_hash` | `afbd2eb0...` | Verified consistent across all 461 cycles |
| `mode` | PAPER | Confirmed |
| `risk_per_trade_pct` | 0.005 (0.5%) | Guardrail override |

**Note:** The `settings.py` default `min_sweep_depth_pct = 0.00286` and the `live_strategy` override `0.0001` are both superseded by the runtime overlay value `0.00649`. The overlay is the source of truth for production.

## Decision Funnel (461 cycles, 2026-05-08 to 2026-05-13)

```
Total decision cycles:              461  (100.0%)
├── Sweep detection layer:          456  ( 98.9% rejected)
│   ├── no_sweep:                   189  ( 41.0%)
│   └── sweep_too_shallow:          267  ( 57.9%)
├── Reclaim / direction layer:        3  (  0.7% rejected)
│   ├── no_reclaim:                   1  (  0.2%)
│   └── uptrend_continuation_weak:    2  (  0.4%)
└── Signal candidates:                2  (  0.4% passed signal layer)
    ├── governance_veto:              1  (  0.2%)  [cooldown_after_loss:5722s]
    └── signal_generated:             1  (  0.2%)  → TRADE EXECUTED
```

### Signal Candidates (2 total)

| Timestamp | Direction | Regime | Confluence | Outcome |
|---|---|---|---:|---|
| 2026-05-10T22:15:00 | LONG | uptrend | 5.55 | → Trade executed |
| 2026-05-10T22:45:00 | LONG | uptrend | 8.05 | → Governance veto (cooldown 95min) |

### Trades (1 total)

| Opened | Closed | Direction | Regime | PnL_R | Exit |
|---|---|---|---|---:|---|
| 2026-05-10T22:15:21 | 2026-05-10T22:15:22 | LONG | uptrend | -0.14 | TP |

**Note:** Trade closed ~1 second after open with exit_reason=TP but with negative pnl_r (-0.14R). This combination (TP exit + loss) is anomalous and likely a paper-fill/bracket evaluation artifact — the paper execution engine fills and evaluates brackets immediately against the snapshot price. This does not affect the signal funnel diagnosis but should be investigated separately as a paper execution realism issue before any live promotion decision.

### Regime Distribution

| Regime | Cycles | % |
|---|---:|---:|
| uptrend | 348 | 75.5% |
| crowded_leverage | 113 | 24.5% |

Market has been predominantly uptrend since deployment, with crowded_leverage phases. No downtrend, normal, or other regime cycles observed.

## sweep_too_shallow Analysis

The 267 `sweep_too_shallow` rejections contain sweep depth data in `details_json` (all rows, full population — no sampling):

| Metric | Value |
|---|---|
| Threshold (`min_sweep_depth_pct`) | **0.00649** (0.649%) |
| Rejected depth min | 0.0008 (0.08%) |
| Rejected depth max | 0.0053 (0.53%) |
| Rejected depth mean | 0.0015 (0.15%) |
| Rejected depth median | 0.0013 (0.13%) |

**The median rejected sweep is 5x shallower than the threshold.** Even the deepest rejected sweep (0.53%) is still 19% below threshold (0.649%). The market is producing sweeps, but they are consistently too shallow for trial-00095's Optuna-optimized geometry.

### sweep_too_shallow by Regime

| Regime | Count |
|---|---:|
| uptrend | 208 |
| crowded_leverage | 59 |

Shallow sweeps occur across both observed regimes, predominantly in uptrend (consistent with overall regime distribution).

## Cycles Per Day

| Date | Cycles | Notes |
|---|---:|---|
| 2026-05-08 | 12 | Deployment day (partial) |
| 2026-05-09 | 96 | Full day (96 = 24h × 4 per hour = every 15m) |
| 2026-05-10 | 96 | Full day — 2 candidates, 1 trade |
| 2026-05-11 | 96 | Full day — 0 candidates |
| 2026-05-12 | 96 | Full day — 0 candidates |
| 2026-05-13 | 65 | Partial day (as of 16:00 UTC) |

Bot is running every 15m cycle consistently. No missed cycles, no errors, no safe mode.

## Verdict: WORKING_AS_DESIGNED_BUT_RARE

### Why NOT SIGNAL_GEOMETRY_TOO_STRICT

The threshold `min_sweep_depth_pct = 0.00649` was Optuna-optimized across 350 trials on 2022-01-01 to 2026-03-28 data. Trial-00095 achieved:
- ER 2.1, PF 4.6, 271 trades over 4+ years
- Walk-forward validation: 2/2 windows passed
- This specific depth threshold was part of the optimization that produced this edge

Relaxing the threshold would:
- Increase trade count but degrade edge quality (proven by grid search: every frequency-improving change degraded ER/PF)
- Violate the Optuna-optimized configuration that IS the edge
- Contradict the context expansion finding: the edge is in the parameters, not the context

### Why WORKING_AS_DESIGNED_BUT_RARE

- 271 trades over 4+ years (backtest) = ~5.5 trades/month average
- But this average includes high-activity and low-activity periods
- Current uptrend market produces shallow sweeps → fewer qualifying setups
- 5 days is too short to judge frequency — need at least 30-60 days
- The 2-5 trades/month estimate in the deployment plan was correct

### Corrected Previous Diagnosis

The earlier strategic consultation (same date) incorrectly stated:
> "The bot generates signals aggressively but governance blocks ~90% as `duplicate_level`"

This was wrong because:
1. The data examined was from May 1 (pre-deployment, different config)
2. The `signal_candidates` table was assumed to have `promoted` and `block_reason` columns (they don't exist)
3. Pre-deployment cycles used different parameters than the trial-00095 runtime overlay

The corrected diagnosis: **signal layer blocks 98.9%, governance blocks 0.2%**. The bottleneck is sweep geometry (depth threshold), not governance.

## Diagnostic Script

The read-only diagnostic script `scripts/diag_live_signal_funnel.py` was created for this analysis. It queries only `decision_outcomes`, `signal_candidates`, `trade_log`, `executable_signals`, and `config_snapshots` tables using correct production schema (no non-existent columns).

Usage:
```bash
python3 scripts/diag_live_signal_funnel.py --since 2026-05-08
```

## Recommendations

### Immediate (no code change)

1. **Continue monitoring trial-00095 as-is.** The bot is working correctly. 5 days is insufficient sample to judge frequency.
2. **Set 30-day review checkpoint** (2026-06-08): Re-run `diag_live_signal_funnel.py`, check if frequency stabilizes toward 2-5/month.
3. **Do NOT relax `min_sweep_depth_pct`** — this would break the Optuna-optimized edge.

### Next Milestone Options

**Option A: TRIAL_00095_CONDITIONAL_EDGE_ANALYSIS_V1** (recommended if concerned about depth threshold)
- **Goal:** Offline analysis of trial-00095's backtest trades vs. sweep depth distribution. Answer: what % of historical trades had depth near the threshold? Is 0.00649 a cliff edge or a smooth transition?
- **Scope:** Read-only analysis of backtest data, no production changes
- **Deliverable:** Depth sensitivity report with confidence intervals on trade frequency given market regime
- **Timeline:** 1-2 days

**Option B: 5M_FEASIBILITY_STUDY_V1** (recommended if ready to pivot timeframe)
- **Goal:** Assess whether 5m frequency resolves the timing incompatibility proven at 15m, without building full infrastructure
- **Scope:** Data availability check, 5m feature feasibility, rough sweep frequency estimate at 5m, cost/benefit analysis
- **Deliverable:** Go/no-go decision document for full 5m infrastructure build
- **Timeline:** 2-3 days

**Recommendation:** Start with **Option A** — it's faster, lower risk, and directly answers the question "is the current market an outlier or the new normal for trial-00095's depth threshold?" If the analysis shows that backtest depth distribution is heavily clustered near 0.00649, that changes the strategic picture. If it's well-separated, then current low frequency is just market conditions and patience is correct.

## Follow-Up Items

### Paper-Fill Artifact (non-blocking)

The single paper trade (2026-05-10) shows `exit_reason=TP` with negative `pnl_r=-0.14R` and closed within ~1 second of opening. This TP+loss combination is inconsistent and suggests a paper execution bracket evaluation issue. This should be investigated separately before any live promotion, but it does not affect the signal funnel diagnosis or the WORKING_AS_DESIGNED_BUT_RARE verdict.

### Security: API Key Exposure (action required)

During diagnostic SSH sessions on 2026-05-13, the production `.env` file contents (including `BINANCE_API_KEY` and `BINANCE_API_SECRET`) were displayed in terminal output. These keys should be treated as potentially compromised. **Recommended action:** rotate Binance API keys at the earliest opportunity and ensure future diagnostic scripts do not cat/display `.env` files.
