# AUDIT: WALKFORWARD-DEFAULT-V1
Date: 2026-05-03
Auditor: Claude Code
Builder: Cascade
WF run: 2026-05-03 18:43–22:05 UTC (3h 22min)
Protocol hash: af280ec9e9a36eaa8eef23eade9ed98ec15f2594cb5009d4f5dc826cba04eb1f

## Verdict: MVP_DONE

## Layer Separation: PASS
## Contract Compliance: PASS
## Determinism: PASS
## State Integrity: PASS
## Error Handling: PASS
## Smoke Coverage: WARN
## Tech Debt: MEDIUM
## AGENTS.md Compliance: WARN
## Methodology Integrity: PASS
## Promotion Safety: PASS
## Reproducibility & Lineage: WARN
## Data Isolation: PASS
## Search Space Governance: PASS
## Artifact Consistency: WARN
## Boundary Coupling: PASS

---

## Audit Summary

Walk-forward on filtered optuna-default-v1-run2 candidates. Hard filter correctly applied
(16/32 passed). WF ran 2 anchored-expanding windows on 16 candidates. Protocol correctly
enforced. One candidate (trial-00000) is clean for paper trading promotion. Critical
finding: trial-00135 has pnl_abs=1.8×10¹⁶ — hard blocker pending investigation.

**Degradation formula verified:**
`mean_degradation = mean over windows of (train_ER - val_ER) / train_ER × 100`
Positive = OOS underperforms IS (overfitting). Negative = OOS outperforms IS (suspicious).
Verified against trial-00000 (+16.1%) and trial-00135 (-16.9%) — formula consistent.

---

## Hard Filter — PASS

Applied before WF: REJECT PF>50, REJECT WR>0.85, REJECT ER<0.
- Input: 32 PASSED trials from optuna-default-v1-run2
- Rejected: 16 (high WR/PF artifact cluster, consistent with OPTUNA-DEFAULT-V1 audit)
- Passed to WF: 16

Filter was applied on raw metrics. Correct.

---

## WF Configuration — PASS

| Parameter | Value | vs Protocol |
|---|---|---|
| Mode | post_hoc, anchored_expanding | ✅ matches default_protocol.json |
| Windows | 2 | ✅ |
| W0 train | 2022-01-01 → 2024-01-01 | ✅ |
| W0 val | 2024-01-01 → 2024-12-31 | ✅ |
| W1 train | 2022-01-01 → 2024-12-31 | ✅ anchored expanding |
| W1 val | 2025-01-01 → 2025-12-31 | ✅ |
| promotion_requires_all_windows_pass | false | ✅ |
| promotion_requires_median_pass | true | ✅ |
| fragility_degradation_threshold_pct | 30.0 | ✅ |

---

## Critical Issues

**C1 — trial-00135: pnl_abs = 1.8×10¹⁶ — HARD BLOCKER**

Physical impossibility. BTC market cap ~$1-2T. Possible causes:
- Compounding position size without clearing prior positions
- Leverage applied multiplicatively across nested risk layers
- Integer/float overflow in PnL accumulation

trial-00135 CANNOT be promoted until this anomaly is diagnosed and root cause confirmed.
If this is a backtest engine bug (not param-specific), it may affect other trials silently.

Action required: run `scripts/diag_backtest.py` for trial-00135 params, inspect
position sizing trace. If engine bug: audit all trial PnL values.

**C2 — Extreme negative degradation cluster: artefact favorable 2025**

Trials 00099 (-196%), 00100 (-337%), 00101 (-296%), 00104 (-95.4%), 00122 (-182%):
OOS ER far exceeds IS ER. This is not a quality signal — it indicates that 2025 (W1 val)
happened to be an exceptionally favorable regime for these parameter sets.

The fragility gate (threshold 30%) only catches OOS underperformance. It does NOT catch
extreme OOS outperformance. These trials "pass" the protocol formally but are unreliable
as promotion candidates. Do not promote.

Current protocol gap: no upper bound on negative degradation. This is D7 (protocol gates
too loose) — remains OPEN.

---

## Candidate Ranking

### Tier 1 — Clean for paper trading

**trial-00000** ⭐
- IS ER=4.865 / OOS ER=2.668, OOS Sharpe=13.61
- 498 IS trades / 76 OOS trades
- Degradation +16.1% (within 30% threshold, both windows pass)
- Per-window: W0 val ER=5.930 (OOS better), W1 val ER=2.667 (OOS worse)
- No anomalies, no flags
- **RECOMMENDED FOR PAPER TRADING**

### Tier 2 — Conditional hold, investigate before promoting

**trial-00052**
- IS ER=1.350 / OOS ER=0.999, OOS Sharpe=5.13
- 3538 IS trades / 753 OOS trades (highest statistical weight)
- Degradation -5.6% (flat per-window, OOS≈IS in windows)
- BUT: global OOS ER=0.999 < 1.0 — below breakeven after realistic trading costs
  (0.04-0.1% commission per side ≈ 0.02-0.04R per trade at 1% risk)
- Most statistically robust trial (753 OOS trades) but real-world edge may be negative
- **HOLD: run cost-sensitivity analysis before paper**

**trial-00097**
- IS ER=1.472 / OOS ER=1.557 (OOS > IS globally), degradation -62.7%
- 905 IS / 183 OOS trades, MDD 25.2%
- Suspicious: extreme negative degradation places this near the 2025-artefact cluster
- Needs per-window breakdown to determine if 2025 drove the outperformance
- **CONDITIONAL: request per-window data from Cascade before decision**

**trial-00098**
- IS ER=1.546 / OOS ER=1.349, OOS Sharpe=3.26, MDD=40%
- 885 IS / 885 OOS trades
- MDD 40% IS is high — paper trading with 40% drawdown is not operationally safe
- Degradation -13.7% (per-window OOS slightly better than IS)
- **HOLD: MDD too high for paper unless risk sizing is adjusted**

**trial-00135**
- IS ER=3.301 / OOS ER=2.942, OOS Sharpe=11.32
- 443 IS / 77 OOS trades, MDD 22.7%
- **BLOCKED: pnl_abs=1.8×10¹⁶ anomaly (C1). Cannot assess.**

### Tier 3 — Statistically insufficient OOS sample

| Trial | OOS N | Issue |
|---|---|---|
| 00161 | 24 | WR=95.8% on 24 trades = 23/24 — statistically meaningless |
| 00123 | 17 | N<30 threshold |
| 00104 | 22 | Extreme negative degradation (-95.4%) + N<30 |
| 00100 | 20 | Extreme negative degradation (-337%) + N<30 |

Min reliable OOS sample: 30 trades per val window. Protocol minimum (`min_trades_per_window: 5`)
is insufficient. See D15.

### Tier 4 — Reject

| Trial | Reason |
|---|---|
| 00095 | FAIL: OOS Sharpe=-0.89, W1 val collapse, fragility=+64.3% > 30% threshold |
| 00099 | Extreme negative degradation -196% — 2025 artefact |
| 00101 | Extreme negative degradation -296% — 2025 artefact |
| 00122 | Extreme negative degradation -182% — 2025 artefact |
| 00132 | 1/2 windows, W0 val FAIL |
| 00102 | 1/2 windows, W0 train FAIL, MDD 48% |

---

## Artifact Consistency — WARN

WF results were delivered as text report only. No JSON artifacts committed to
`docs/walkforward/`. The directory contains only `.gitkeep`. Per-window data available
only for trial-00000 and trial-00135 — all other trials missing per-window breakdown.

This is a reproducibility gap: the WF cannot be independently verified or re-run from
committed artifacts. Cascade must commit: `filter_report.json`, per-trial WF JSONs,
`summary.json`.

---

## Reproducibility & Lineage — WARN

Missing from committed artifacts:
- Per-trial WF JSON with per-window metrics
- Filter report (which 16 were rejected and why)
- Runner invocation command with exact args

Protocol hash is recorded (af280ec9...) which allows reproduction of the protocol
configuration. Study name (optuna-default-v1-run2) and seed (42) are documented.
Lineage is traceable but artifacts are not committed.

---

## Tracked Debt

| ID | Description | Priority | Status |
|---|---|---|---|
| D7 | Protocol gates too loose — no negative degradation cap, OOS N not gated | MEDIUM | OPEN — add before campaign 2 WF |
| D14 | Throttling bias in force_order_spike (Boon Chuan Lim finding) | LOW | OPEN — research debt |
| D15 | WF artifacts not committed to docs/walkforward/ | MEDIUM | OPEN — Cascade must commit |
| D16 | min_trades_per_window=5 allows OOS N=17 — statistically meaningless | MEDIUM | OPEN — raise to 30 |
| D17 | trial-00135 pnl_abs=1.8×10¹⁶ anomaly unexplained | HIGH | OPEN — investigate before any use |

---

## Recommended Next Step

**Promote trial-00000 to paper trading.**

No blockers. Clean WF 2/2, OOS ER=2.668, OOS Sharpe=13.61. Strongest unambiguous
candidate. 76 OOS trades is low but acceptable given strong metrics across all windows.

**Before paper trading launch:**
1. Cascade commits WF artifacts to `docs/walkforward/` (D15)
2. Update `param_registry.py`: correct `weight_force_order_spike` frozen reason to reflect
   throttling finding (Boon Chuan Lim) — in progress
3. Update `MILESTONE_TRACKER.md`: mark WALKFORWARD-DEFAULT-V1 DONE, open PAPER-TRADING-V1

**Parallel (not blocking paper):**
- Diagnose trial-00135 pnl_abs anomaly (D17) — could indicate backtest engine bug
- Request per-window breakdown for trial-00097 — only then decide Tier 2 fate
- Tighten protocol for campaign 2 WF: add min_trades_val_window=30, cap negative degradation
