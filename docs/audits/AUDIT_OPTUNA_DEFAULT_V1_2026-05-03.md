# AUDIT: OPTUNA-DEFAULT-V1
Date: 2026-05-03
Auditor: Claude Code
Commit: 1a70e0f (WAL fix) + bcf8615 (Cascade MILESTONE_TRACKER update)

## Verdict: MVP_DONE

## Layer Separation: PASS
## Contract Compliance: PASS
## Determinism: PASS
## State Integrity: PASS
## Error Handling: PASS
## Smoke Coverage: PASS
## Tech Debt: MEDIUM
## AGENTS.md Compliance: WARN
## Methodology Integrity: WARN
## Promotion Safety: WARN
## Reproducibility & Lineage: PASS
## Data Isolation: PASS
## Search Space Governance: WARN
## Artifact Consistency: PASS
## Boundary Coupling: PASS

---

## Audit Summary

Two-run campaign. Run 1 (50 trials) failed — all returned penalty. Root causes identified and
fixed. Run 2 (200 trials) succeeded — 32 PASSED candidates found.

**Run 1 failure root causes (both confirmed):**
1. `db_snapshot.py` used `shutil.copy2` on WAL-mode DB → snapshots missed committed WAL data →
   backtests ran on incomplete DB → 0 trades (fixed in commit `1a70e0f`)
2. Constraint violation rate ~72% on 35-param search space → only 14/50 ran backtest;
   those 14 had degenerate params (0 trades) due to no warm-start seeding

**Run 2 configuration:**
- study_name: `optuna-default-v1-run2`
- protocol: `default_protocol.json` (post_hoc, anchored_expanding)
- window: 2022-01-01 → 2026-03-28 (1547 days, 2 WF windows)
- n_trials: 200, seed: 42, warm_start_from_store: True
- Pre-flight: 2h15min (3 full DB scans, 3.7GB DB, 135MB free RAM)

**Run 2 final breakdown (200 trials):**

| Reason | Count | % |
|---|---|---|
| MIN_TRADES=0 | 75 | 37.5% |
| PASSED | 32 | 16.0% |
| high_vol_leverage constraint | 30 | 15.0% |
| participation_min constraint | 22 | 11.0% |
| combo constraints | 16 | 8.0% |
| MIN_TRADES >0 <100 | 14 | 7.0% |
| allow_long + allow_uptrend | 10 | 5.0% |

Constraint violation rate: 78/200 = 39% (improved vs estimated 72% due to TPE learning from
warm-start). WAL fix confirmed working: `trades_count=46` in early trials, rising to 885-3538
in legitimate candidates.

---

## Candidate Analysis — 32 PASSED Trials

### Population A: Legitimate candidates

| Trial | ER | PF | MDD | Trades | WR | Sharpe | Status |
|---|---|---|---|---|---|---|---|
| 00000 | 4.87 | 6.85 | 5.4% | 498 | 69.7% | 9.23 | ✅ warm-start baseline |
| 00052 | 1.35 | 2.29 | 6.0% | 3538 | 44.7% | 6.19 | ⚠️ trade count outlier |
| 00098 | 1.55 | 1.57 | 40.0% | 885 | 28.8% | 3.22 | ✅ realistic, MDD high |
| 00097 | 1.47 | 1.81 | 25.2% | 905 | 32.7% | 3.85 | ✅ realistic |
| 00099 | 0.95 | 2.32 | 32.7% | 237 | 39.7% | 4.18 | ✅ realistic |
| 00104 | 0.91 | 2.29 | 31.9% | 163 | 41.7% | 5.21 | ✅ realistic |
| 00123 | 0.94 | 2.11 | 13.2% | 139 | 43.9% | 5.14 | ✅ best MDD in class |
| 00135 | 3.30 | 3.26 | 22.7% | 443 | 60.3% | 12.33 | ⚠️ borderline WR |
| 00091 | -0.75 | 0.33 | 62.2% | 307 | 19.2% | -7.89 | ❌ reject |

### Population B: Confirmed artifacts — DO NOT PROMOTE

| Trial | ER | PF | MDD | Trades | WR | Sharpe | Reason |
|---|---|---|---|---|---|---|---|
| 00136 | 5.66 | 351,000,000,000 | 2.6% | 228 | 99.1% | 15.06 | PF=351B = no losses |
| 00141 | 4.06 | 1,507,074 | 4.5% | 160 | 98.1% | 28.51 | PF=1.5M = no losses |
| 00184 | 2.87 | 40.8 | 4.1% | 270 | 97.4% | 28.25 | WR=97% impossible |
| (others 136+) | — | — | — | — | 96-99% | 15-28 | same artifact pattern |

**Artifact pattern diagnosis:** TPE converged on parameter region with:
- Ultra-restrictive entry (confluence_min ~4.0-4.5) → ~40 entries/year
- Stop-loss so wide (`invalidation_offset_atr` near maximum 5.0) it rarely triggers
- Long hold time (`max_hold_hours` near maximum 72h) → positions held to profit
- In trending BTC 2023-2026 bull market → trades almost never stopped out → WR 96-99%
- PF → ∞ as losing trades approach zero

This is NOT an edge. It is a degenerate exploitation of the backtest framework by extreme
parameter values. No stop = no losses = infinite PF. The same parameters in a ranging or bear
market (2022 drawdown) would produce catastrophic real losses.

**Critical note on WF gate adequacy:**
`default_protocol.json` gates (`min_expectancy_r=0.0`, `max_dd=50%`, `fragility_degradation=30%`)
are insufficient to filter these artifacts. An artifact with Sharpe=28 that degrades 30% OOS
still shows Sharpe=19.6 — still "passes" the protocol. WF gates were designed for normal
strategies, not infinite-PF exploitation.

---

## Critical Issues

**C1 — Promotion Safety: artifact filter REQUIRED before walk-forward**

Artifacts in population B must be hard-blocked before walk-forward is run. If WF runs on
trial-00136 (PF=351B), it may "pass" on WF windows that include the 2023-2026 bull run,
producing a fraudulent recommendation artifact.

**Hard filter rule (mandatory, apply before WF):**
- REJECT: `profit_factor > 50`
- REJECT: `win_rate > 0.85`
- REJECT: `expectancy_r < 0`

Applying these filters reduces the candidate pool from 32 to approximately 7-8 legitimate
trials for walk-forward.

**C2 — Search Space Governance: 84% trial failure rate**

84% of trials either violated constraints or returned 0 trades. Root causes:
1. Constraint violation rate 39% — 4 correlated constraints on active params
2. Zero-trade rate 37.5% — degenerate weight combinations (all weights near 0)

For the NEXT campaign, `default_protocol.json` should include `active_params_whitelist` to
reduce the effective search space. 35 active params is unmanageable for 200 trials.

**C3 — AGENTS.md Compliance: branch mismatch**

Cascade committed MILESTONE_TRACKER updates to `modeling-context-closure` instead of the
active audit branch `claude/audit-wf-light-protocol-ZXDA9`. Branch discipline must be
maintained. All commits in this session should be on the designated branch.

---

## Warnings

**W1 — trial-00052: trade count outlier (3538 trades / 4 years = 2.4/day)**

For a sweep/reclaim strategy, 2.4 trades/day is unusually high. The baseline (trial-00000)
generates 498 trades (0.34/day). A 7x increase suggests very loose confluence conditions
(low `confluence_min` or near-zero individual signal weights). This is not automatically an
artifact — loose confluence can be a valid strategy variant — but it warrants parameter
inspection before WF. Check: what is `confluence_min` for this trial?

**W2 — trial-00135: borderline WR (60.3%)**

WR=60.3% is high but not impossible for a sweep strategy with tight entry. PF=3.26, MDD=22.7%.
The key question: is this WR achieved via genuine signal quality or via stop exploitation?
Inspect `invalidation_offset_atr` for this trial before including in WF.

**W3 — Protocol WF gates too loose for artifact detection**

`min_expectancy_r_per_window=0.0` and `fragility_degradation_threshold_pct=30.0` will not
catch high-PF artifacts. If a degenerate trial survives hard filter (C1) and enters WF,
it may produce a fraudulent recommendation. Consider tightening for future campaigns:
- `min_profit_factor_per_window: 1.2`
- `max_drawdown_pct_per_window: 35.0`

---

## Observations

- Pre-flight took 2h15min: 3 full scans of 3.5GB DB in 3.7GB RAM server. For future campaigns,
  either increase server RAM or pre-checkpoint DB to speed up `check_signal_health` scan.
- TPE converged well: constraint violation rate dropped from 72% (run 1 random) to 39%
  (run 2 with warm-start + TPE learning). Warm-start worked as intended.
- trial-00000 (baseline warm-start) produced ER=4.87, Sharpe=9.23 — strong result.
  This is a known-good parameter set (Trial #63 lineage). Valid WF candidate.
- 2 WF windows (train 730d + val 365d, anchored expanding) is adequate for 2022-2026.

---

## Recommended Next Step

**Run walk-forward on filtered candidate pool only.**

Apply hard filter first (C1), then run WF on the ~7-8 legitimate trials:

Priority WF candidates: `00000, 00097, 00099, 00104, 00123` (realistic metrics, no flags)
Secondary (with param inspection first): `00052` (check confluence_min), `00135` (check
invalidation_offset_atr), `00098` (high MDD — decide if acceptable)

Exclude entirely: `00091` (negative ER), `00136`, `00141`, `00184`, all trials with WR>85%

Walk-forward will produce the final recommendation artifacts. Only after WF PASS on a
legitimate candidate should promotion to paper trading be considered.

---

## Tracked Debt

| ID | Description | Priority | Status |
|---|---|---|---|
| D6 | 35-param active search space → 84% trial failure rate | MEDIUM | OPEN — add active_params_whitelist to next protocol |
| D7 | WF protocol gates too loose for artifact detection | MEDIUM | OPEN — tighten for next campaign |
| D8 | Server RAM (3.7GB) too small for 3.5GB DB — 2h15min pre-flight | LOW | OPEN — accept for now |
| D9 | Branch mismatch: Cascade committed to wrong branch | LOW | CLOSED — noted, correct in next session |
| D5 | `_stream_rows_from_zip` misnomer in backfill_oi.py | LOW | OPEN (cosmetic) |
