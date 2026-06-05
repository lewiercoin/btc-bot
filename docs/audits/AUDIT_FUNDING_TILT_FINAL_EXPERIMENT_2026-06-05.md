# AUDIT: FUNDING_TILT_FINAL_EXPERIMENT
Date: 2026-06-05
Auditor: Claude Code
Commit: c9e06d3 (deploy/multi-asset-paper-v1)
Pre-registration: docs/FUNDING_TILT_FINAL_EXPERIMENT_PREREGISTRATION_2026-06-05.md (frozen b8dd9be)

## Verdict (deliverable quality): MVP_DONE
## Experiment result: FAIL (mechanical, against frozen gates)
## Strategic consequence: terminal wind-down rule fires (see Recommended Next Step)

The diagnostic is methodologically sound and produced an honest, multiply-determined
negative result. This is a good deliverable reporting a dead strategy.

## Layer Separation: PASS
Isolated research diagnostic. No changes to core/, execution/, orchestrator.py,
settings.py. compileall passed across the live path.

## Contract Compliance: PASS
All frozen gates implemented mechanically (funding_tilt_edge_discovery_v1.py:
stop_reasons assembled from fold ER<=0, degradation, control failures). Verdict
JSON ends in PASS|FAIL as required.

## Determinism: PASS
RANDOM_SEED fixed; controls seeded `RANDOM_SEED + fold_index`; selection is a
deterministic sort key (mean OOS ER, then PF, then trades).

## State Integrity: PASS
Read-only DB access. No mutation of source data.

## Error Handling: PASS
Explicit table/column coverage check; fold-4 OOS end capped to DB max with explicit
reporting; no silent fold shifting.

## Smoke Coverage: WARN
Funding-sign unit tests (2) pass and hand-verify the sign on worked examples — the
mandatory pkt-3 gate is satisfied. Caveats: (a) full pytest suite blocked locally by
missing `pytest-cov`; (b) run used `storage/btc_bot.db` with data through 2026-05-25
— provenance vs the canonical server DB should be confirmed, though the FAIL is robust
to data quibbles (see below).

## Tech Debt: LOW

## Methodology Integrity: PASS
Nested selection prevents OOS contamination (folds 1-3 select, fold 4 untouched).
Controls are honest and discriminating. Critically, the controls EXPOSE that the
apparent edge is largely regime beta, not funding timing (fold_1 random beats main).
No overfit claim is made.

## Promotion Safety: PASS
Hard FAIL. No promotion path triggered. No paper/live deployment in scope.

## Reproducibility & Lineage: PASS
Selected cell (W60/Z2.5/H14), folds, seed, commit, pre-registration hash all explicit.
Only open item: canonical DB provenance (WARN above).

## Data Isolation: PASS
## Search Space Governance: PASS — 3 params, 27 cells, no post-hoc widening.
## Artifact Consistency: PASS — JSON, 27-cell grid, and main-vs-control table reconcile
(mean of fold_1..3 main ER = (1.5895 + 1.0546 - 0.3720)/3 = 0.7573 = selected cell's
selection_mean_oos_er; pooled overall_er 0.5515 over 104 trades consistent).
## Boundary Coupling: PASS

## Why the FAIL is honest, not a bug (four-vector check)
1. Funding sign: unit-tested correct → funding aids the trade; it still fails. FAIL strengthened.
2. Nested selection: verified; fold 4 played no role in selecting the cell.
3. Lookahead: would inflate results, cannot manufacture a FAIL.
4. Controls: a broken harness flatters main; here a control (fold_1 random) BEATS main.

## Result summary
- Selected cell W60/Z2.5/H14: OOS ER by fold = +1.589 (2022), +1.055 (2023),
  **-0.372 (2024)**, **+0.033 (2025-26)**.
- Degradation selection→confirmation: **95.6%** (gate <40%).
- Control failures: fold_1 random, fold_3 inverse, fold_4 inverse.
- Tail (no stop): worst trade **-18.54R**, max drawdown **22.08R**.

Interpretation: funding-tilt "worked" only in the 2021-2022 extreme-leverage-unwind
regime (persistent extreme funding + violent deleveraging). As funding normalized
from 2023, the edge decayed to nothing and its sign became unstable (inverse beats
main in the two most recent folds). Even in its best year it did not beat a
same-structure random entry — i.e., it captured directional beta, not a funding
timing edge. The grid-robustness "27/27 positive in folds 1-3" is explained by the
same shared bear-beta, not by a genuine parameter-robust edge.

## Critical Issues (must fix before next milestone)
None in the deliverable.

## Warnings (fix soon)
- Confirm canonical DB provenance for any future re-run.
- Restore `pytest-cov` (or strip repo addopts) so the full suite runs in CI.

## Observations (non-blocking)
- No-stop, time-based exit produces ruinous single-trade tails; any future revival of
  a funding idea must include a stop and be re-tested from scratch.

## Recommended Next Step
The frozen, pre-committed decision rule fires: **FAIL → wind down the trading thesis.**
Edge families now exhausted under honest tests: sweep/reclaim/SMC structure (dead — 0
live trades, WF passed=false), volatility breakout (ER -0.092), regime-shift ADX/CHOP
(ER -0.027), regime-shift HMM (ER -0.122), liquidation burst 15m/5m (timing failure),
funding-tilt directional (this FAIL). Preserve the data + research/validation harness +
honest audit culture as the retained value. Executing the real-world wind-down (stop
the live paper bot, reconcile branches, formally close trial-00095 as DEAD, archive)
is the product owner's call — recommended, awaiting explicit go.
