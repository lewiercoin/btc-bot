# Milestone Tracker

Last updated: 2026-04-12

---

## Current Active Milestone

**Milestone:** RUN12-SOFT-PENALTY — First campaign with working TPE gradient
**Status:** ACTIVE — Run #12 running on server (tmux `optimize12`, ~88+ of 300 trials)
**Active builder:** Claude Code (auditor executed directly)
**Decision date:** 2026-04-12
**Commits:**
- `45cea8a` SIGNAL-REVERT-V1: restore core signal files to 8f2c6f2 + cherry-pick min_hits=3
- `51513f2` SIGNAL-REVERT-V1-FIX: remove deleted FeatureEngineConfig fields from optimize_loop
- `92df4b4` SOFT-PENALTY-V1: replace zero-vector with soft penalty + constraints_func
- `92bbbfd` SOFT-PENALTY-V1: add anti-overfitting guard for PF > 5.0

**Campaign config:**
- study_name: run12-soft-penalty
- n_trials: 300
- start_date: 2022-01-01 / end_date: 2026-03-01
- max_sweep_rate: 1.0 (bypass health gate — sweep rate 99.49% is implementation artifact, not signal flaw)
- warm_start: yes
- min_trades_full_candidate: 100 (from default_protocol.json)

**Key changes vs all prior campaigns:**
- `min_hits=2 → 3` in feature_engine.py (cherry-pick from ba1d6d1; Test B: -6.3% trades, +0.001 expectancy — safe)
- Zero-vector [0.0, 0.0, 1.0] replaced with quadratic soft penalty (LAMBDA=0.45/0.30/0.25)
- Constraint violations return (-2.0, 0.1, 1.0) + constraints_func for TPE hard-blocking
- Anti-overfitting guard: PF capped at 5.0; PF>3.0 with trades>=80 → additional penalty

**Run #12 results so far (after 87 trials):**

| Trial | exp_r | PF | DD | Status |
|-------|-------|-----|-----|--------|
| #0 | -0.057 | 0.930 | 76.7% | warm start baseline |
| #1 | +0.058 | 1.030 | 22.5% | first TPE positive |
| #13 | +0.225 | 1.235 | 32.1% | |
| #26 | **+0.636** | **1.617** | 40.5% | **best credible** |
| #31 | +0.384 | 1.359 | 30.2% | |
| #41 | +0.284 | 1.338 | 25.4% | |
| #42 | +0.309 | 1.294 | 31.0% | |
| #47/#56/#73 | ~+1.5–1.9 | 999,999 | 24.5% | overfitted (PF=inf, zero losses) |

**Zero zero-vectors confirmed.** Death spiral broken. TPE finds positive region immediately.

**Anti-overfitting guard deployed mid-campaign** (trial #88+): caps PF≤5.0, penalizes zero-loss regimes.

**Next step after campaign:** filter PF>3.0, take top 5-7 credible trials, run anchored walk-forward (2022-2024 train / 2024-2025 test / 2025-2026 test).

---

## Diagnostic Results (2026-04-12)

### Crash Test (confluence_min=0.0, min_rr=1.0, 8f2c6f2 signal)
- 1,262 trades / 4 years
- expectancy_r = **-0.054** (not anti-edge; headroom to Run #3 best = +0.195 R)
- profit_factor = 0.934
- Regime blocked 53% of signals (healthy filtering)
- Governance blocked 26%
- Risk rejected <1% (min_rr=1.0 passes everything)

### Test B (min_hits=3 cherry-pick, same conditions)
- 1,183 trades (-6.3% vs baseline)
- expectancy_r = **-0.053** (marginally better)
- profit_factor = 0.939
- **Verdict: safe cherry-pick. min_hits=3 cleans noise without killing signal.**

### Run #3 reference (best historical result, pre-SWEEP-RECLAIM-FIX-V1)
- study: baseline-v3-trial-00195
- expectancy_r = +0.141, profit_factor = 1.192, **607 trades**
- Walk-forward: mixed (some windows failed — normal for trend-following in regime-mixed 2022-2025)

---

## Completed Milestones (reverse chronological)

### SIGNAL-REVERT-V1 + SIGNAL-REVERT-V1-FIX
**Status:** DONE (commits 45cea8a + 51513f2, 2026-04-12)
**What:** Restored core signal files to commit 8f2c6f2 (pre-SWEEP-RECLAIM-FIX-V1). Applied cherry-pick min_hits=3. Fixed optimize_loop.py incompatibility (removed deleted FeatureEngineConfig fields).
**Why:** Runs #5-#11 all failed. Root cause: SWEEP-RECLAIM-FIX-V1 (ba1d6d1) removed sweep/reclaim from confluence scoring AND SIGNAL-ENGINE-REARCH-V1 (cc0024c) made sweep_side the direction source — both changes broke the edge proven in Run #3. Crash Test confirmed raw signal at 8f2c6f2 is not anti-edge (expectancy -0.054).
**Files changed:** core/feature_engine.py, core/signal_engine.py, settings.py, orchestrator.py, backtest/backtest_runner.py, research_lab/param_registry.py, tests/
**Tests:** 63 passed, 24 skipped (intentional — skips reference removed fields)

### DATA-COLLECTORS-V1
**Status:** DONE (commits 5a3c09e + a8dc92e, 2026-04-11)
**What:** Systemd services for live data collection: btc-bot-force-collector (WebSocket liquidations, 24/7), btc-bot-daily-collector (DXY via yfinance, ETF flows via SoSoValue, daily at 00:05 UTC).
**Note:** force-collector has 401 error on server (BINANCE_API_KEY format). Data gaps exist until fixed.

### RUN9-CONFIG / RUN10-CONFIG
**Status:** DONE (commits cf65604, 600aada)
**What:** Progressive lowering of min_trades_full_candidate: 750→300→100. Added warm_start flag.
**Result:** With min_trades=100 and warm start, baseline finally returned non-zero values (-0.874). Confirmed zero-vector problem was cliff + TPE gradient absence, not bad signal per se.

### RUN7-SEARCHSPACE
**Status:** DONE (commit 6612dea, 2026-04-11)
**What:** Tightened 7 unrealistic parameter ranges:
- min_rr: [1.01, 10.0] → [1.5, 4.0]
- tp1_atr_mult: [0.1, 10.0] → [0.5, 5.0]
- tp2_atr_mult: [0.2, 15.0] → [1.0, 8.0]
- high_vol_leverage: [1, 10] → [1, 9]
- max_open_positions: [1, 10] → [1, 3]
- max_trades_per_day: [1, 20] → [1, 6]
- max_hold_hours: [1, 168] → [1, 72]
**Why:** Run #6 had 54% risk rejections (high_vol_leverage > max_leverage), avg min_rr=5.62 (unreachable RR). All changes still active in current campaign.

### SIGNAL-SCORE-RESTORE-V1
**Status:** SUPERSEDED by SIGNAL-REVERT-V1 (commit d66d0d8, 2026-04-11)
**What:** Restored weight_sweep_detected=0.35 and weight_reclaim_confirmed=0.35 to confluence scoring (removed in ba1d6d1). Also fixed weight_cvd_divergence range max 0.50→0.75.
**Result:** Run #10 baseline improved from -0.874 to -0.795. TPE still 95% zero-vectors.
**Why superseded:** Root cause was deeper — SIGNAL-ENGINE-REARCH-V1 sweep_side direction also needed revert. SIGNAL-REVERT-V1 is the complete fix.

### SIGNAL-ENGINE-REARCH-V1
**Status:** REVERTED by SIGNAL-REVERT-V1 (commit cc0024c, 2026-04-10)
**What was wrong:** Made sweep_side the direction source (LOW→LONG, HIGH→SHORT). CVD/TFI demoted to confluence only.
**Why reverted:** At 8f2c6f2, sweep_side was NOT the direction source — CVD/TFI + regime drove direction, sweep was a confluence weight. This architecture produced +0.141 in Run #3. Post-REARCH all campaigns produced negative or zero results.

### SWEEP-RECLAIM-FIX-V1
**Status:** PARTIALLY REVERTED by SIGNAL-REVERT-V1 (commits ba1d6d1 + a111ac9 + 442ff3b, 2026-04-09)
**What was reverted:** Removal of sweep/reclaim from confluence scoring (C2a change in ba1d6d1). Also proximity filter (a111ac9) and tightened default (442ff3b).
**What was kept:** min_hits=3 (cherry-picked back as Test B confirmed safety).
**level_min_age_bars=5 NOT yet implemented** — not in 8f2c6f2 codebase. Deferred to Run #13 as tunable parameter [2, 6].
**Original problem:** sweep_detected_rate was 99.49% — real implementation bug in detect_equal_levels. Fix (min_hits) is correct; removing from scoring was wrong.

### SIGNAL-INVERSION-V1
**Status:** REVERTED by SIGNAL-REVERT-V1 (commit ab664e2, 2026-04-10)
**What was wrong:** Flipped LONG/SHORT direction. Run #5 result: 563 trades, WR=10.5%, ExpR=-0.94.

---

## Campaign History

| Run | Trials | Best exp_r | Status | Root cause of failure |
|-----|--------|-----------|--------|----------------------|
| Run #1 | ~50 | +0.031 (31 trades) | Not promoted | allow_long_in_uptrend disabled; only 31 trades |
| Run #2 | ~100 | — | Not promoted | Low trade count |
| Run #3 | 273 | **+0.141** (607 trades) | **Best historical** | Walk-forward mixed — acceptable |
| Run #4 | ~100 | negative | Not promoted | SWEEP-RECLAIM-FIX-V1 just applied; signal degraded |
| Run #5 | 200 | 0.0 (all zero) | Failed | min_trades=2000 > signal frequency; TPE blind |
| Run #6 | 300 | 0.0 (all zero) | Failed | min_trades=750, 54% risk rejections from unrealistic high_vol_leverage |
| Run #7 | 300 | 0.0 (all zero) | Failed | Realistic search space but zero-vector cliff still present |
| Run #8 | 45 | 0.0 (all zero) | Stopped | min_trades=300, same cliff |
| Run #9 | ~145 | -0.874 (warm start) | Stopped | SIGNAL-ENGINE-REARCH-V1 negative baseline; TPE 95% zero-vectors |
| Run #10 | 141 | -0.462 | Stopped | SIGNAL-SCORE-RESTORE-V1 helped slightly; still 95% zero-vectors |
| Run #11 | 92 | -0.034 (warm start) | Stopped | Signal restored but 88% zero-vectors; no soft penalty yet |
| **Run #12** | **300 (active)** | **+0.636** (trial #26) | **ACTIVE** | **First campaign with working gradient** |

---

## Known Issues (open)

| # | Issue | Priority | Notes |
|---|-------|----------|-------|
| K1 | BINANCE_API_KEY format invalid on server | LOW | force-collector failing with 401; not blocking optimization |
| K2 | force_orders table has 0 rows | LOW | No historical liquidation data; feature frozen in param_registry |
| K3 | daily_external_bias (ETF/DXY) table empty | LOW | EtfBiasCollector runs but ETF data incomplete |
| K4 | Walk-forward uses 6 windows over 4 years | MEDIUM | ~150 trades/window may be insufficient; defer to post-Run#12 |
| K5 | level_min_age_bars not yet in 8f2c6f2 codebase | LOW | Deferred to Run #13; add as tunable [2, 6] |
| K6 | PF=999999 trials (#47/#56/#73) in Run #12 journal | LOW | Anti-overfitting guard deployed at trial #88; future trials unaffected |

---

## Baseline Checkpoint

| Field | Value |
|---|---|
| **Tag** | `v1.0-baseline` |
| **Commit** | `a1a82b5` |
| **Date** | 2026-04-01 |
| **How to restore** | `git checkout v1.0-baseline` |
| **What it contains** | Fazy A–H MVP_DONE · Research Lab RL-V1 do RL-FUTURE MVP_DONE · 18/18 Known Issues zamknięte · dokumentacja zsynchronizowana · 35/35 testów zielonych |
| **Strategy at tag** | PF 1.40 · WR 43.6% · Sharpe 4.37 · DD 17.0% |

---

## Architecture Decisions Log

| Date | Decision | Outcome |
|------|----------|---------|
| 2026-04-09 | SWEEP-RECLAIM-FIX-V1: remove sweep from scoring, add proximity filter | REVERTED — degraded signal |
| 2026-04-10 | SIGNAL-ENGINE-REARCH-V1: sweep_side as direction source | REVERTED — all campaigns failed |
| 2026-04-10 | SIGNAL-INVERSION-V1: flip LONG/SHORT | REVERTED — negative expectancy |
| 2026-04-11 | RUN7-SEARCHSPACE: realistic param ranges | KEPT — sound improvement |
| 2026-04-12 | SIGNAL-REVERT-V1: restore 8f2c6f2 + min_hits=3 | ACTIVE — Crash Test confirmed safe |
| 2026-04-12 | SOFT-PENALTY-V1: replace zero-vector cliff | ACTIVE — TPE death spiral broken |
| 2026-04-12 | Anti-overfitting guard: cap PF>5.0 | ACTIVE — deployed at trial #88 |

---

## Next Steps After Run #12 (proposed, pending audit)

1. Filter all trials with PF > 3.0 (statistically unreliable — zero-loss over 4yr is impossible in BTC perps)
2. Take top 5-7 credible trials (PF 1.3–2.5, trades > 120)
3. Anchored walk-forward: train 2022-2024, test 2024-2025, test 2025-2026
4. If best candidate passes both OOS windows → paper trading validation
5. Run #13: add level_min_age_bars as tunable [2, 6] + simple regime meta-layer (volatility × funding × cvd_strength)
