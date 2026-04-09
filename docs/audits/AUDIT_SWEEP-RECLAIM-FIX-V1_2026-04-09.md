# AUDIT: SWEEP-RECLAIM-FIX-V1
Date: 2026-04-09
Auditor: Claude Code
Commit: 442ff3b

## Verdict: MVP_DONE

## Layer Separation: PASS
## Contract Compliance: PASS
## Determinism: PASS
## State Integrity: PASS
## Error Handling: PASS
## Smoke Coverage: PASS
## Tech Debt: LOW
## AGENTS.md Compliance: PASS
## Methodology Integrity: PASS
## Promotion Safety: N/A
## Reproducibility & Lineage: PASS
## Data Isolation: PASS
## Search Space Governance: PASS
## Artifact Consistency: N/A
## Boundary Coupling: PASS

## Critical Issues (must fix before next milestone)
None.

## Warnings (fix soon)
- ACTIVE count rose from 44 → 45 (sweep_proximity_atr added). Optuna budget
  still 200 trials — acceptable for now but worth noting.

## Observations (non-blocking)
- Proximity filter default calibrated at 0.4×ATR based on 3-month replay
  (2025-01-01..2025-04-01). This value is ACTIVE in Optuna — campaigns will
  explore [0.2, 2.0] range automatically.
- Intermediate LOOKS_DONE verdict was due to auditor simulation error: sweep%
  simulation counted only equal_lows, missing equal_highs contribution. Final
  smoke on live data confirms criterion met.
- sweep+reclaim (true signal) rate: 5.30% (458/8641 bars). Comparable to
  pre-fix reclaim rate (~7.1%) — signal volume preserved, quality improved.

## Acceptance Criteria — all met
| Criterion | Result |
|---|---|
| compileall clean | PASS |
| pytest 60/60 green | PASS |
| sweep_detected < 50% (default config, 2025-Q1) | PASS — 48.07% |
| level_min_age_bars + min_hits ACTIVE in registry | PASS |
| sweep_proximity_atr ACTIVE, range [0.2, 2.0] | PASS |
| confluence_min default = 0.75 | PASS |
| weight_sweep_detected + weight_reclaim_confirmed FROZEN | PASS |

## Recommended Next Step
OPTUNA-UTILITY-V1. Handoff: docs/handoffs/HANDOFF_OPTUNA_UTILITY_V1.md.
Run #4 (first clean campaign) after OPTUNA-UTILITY-V1 is deployed.
