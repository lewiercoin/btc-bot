# AUDIT: RESEARCH-LAB-FIXES
Date: 2026-04-08
Auditor: Claude Code
Commit: 903d6f1

## Verdict: DONE

All 5 deliverables correct. Root cause of C3 properly diagnosed and fixed. No regressions. 53/53 tests green.

## Layer Separation: PASS
Changes confined to: shell scripts in `scripts/server/`, deploy docs, protocol config JSON. No production Python code touched.

## Contract Compliance: PASS
`default_protocol.json` schema unchanged — only values updated. Research lab loads protocol via `protocol.py` which reads these fields by name; no breaking change.

## Determinism: PASS
Protocol change (train_days, validation_days, step_days, min_trades_per_window) affects walk-forward window generation deterministically. Existing trials in research_lab.db were generated under old protocol — new runs will use new protocol. No cross-contamination possible (protocol_hash in lineage).

## State Integrity: PASS
Auto-cleanup (D2) runs after optimize completes and report is written. Cleanup failure is non-blocking (`|| true`). No state integrity risk.

## Error Handling: PASS
D1 root cause: `set -eu` + `[ -s "$FILE" ] && cat` — when file is empty, `&&` short-circuits with exit 1, which `set -e` treats as fatal. Fix (unconditional `cat` on empty file = no-op, exits 0) is correct and minimal.

## Smoke Coverage: PASS
53/53 tests green. Shell script changes are not unit-testable in the Python test suite — covered by operational smoke (next optimize run on server).

## Tech Debt: LOW
One observation noted below.

## AGENTS.md Compliance: PASS
Single commit, WHAT/WHY/STATUS format. Does not self-mark as DONE.

## Methodology Integrity: PASS
Protocol change is documented and justified. `walkforward_mode` remains `post_hoc` — no methodology scope change. New window sizes (180/90/45) and `min_trades_per_window=5` are calibrated to observed strategy frequency (~8 trades/year). This is correct methodology adjustment, not overfitting gate relaxation.

## Promotion Safety: PASS
Hard gate logic unchanged. `walkforward_not_passed` still blocks approval bundle generation. Only the thresholds that define "passed" are adjusted.

## Reproducibility & Lineage: PASS
`protocol_hash` in trial lineage will reflect the new protocol values. Old and new runs are distinguishable by hash.

## Data Isolation: PASS
## Search Space Governance: PASS
## Artifact Consistency: PASS
## Boundary Coupling: PASS

---

## Critical Issues

None.

---

## Warnings

None.

---

## Observations

### O1 — cleanup_snapshots.sh path assumption

D2 cleanup call:
```sh
if [ -x "scripts/server/cleanup_snapshots.sh" ]; then
```

This uses a relative path. `run_optimize.sh` already requires CWD = repo root (line 5 check). Consistent — no issue in practice. But `-x` checks execute permission, not existence. If the file exists but is not executable (e.g. after fresh git clone without chmod), cleanup is silently skipped. Non-blocking — cleanup failure is `|| true` anyway.

### O2 — min_trades_full_candidate remains 30

`default_protocol.json` still has `min_trades_full_candidate=30`. With the strategy generating ~31 trades over 4 years in the best trial, this threshold is borderline. If next run finds candidates with fewer full-period trades, they will be rejected at this gate. Monitor after run #2 — may need adjustment to 15-20.

---

## Recommended Next Step

Push and run optimize run #2 on server:
```sh
sh scripts/server/run_optimize.sh baseline-v2 200 2022-01-01 2026-04-01
```
200 trials with new protocol. Auto-cleanup will run after. Report to Claude Code when done.
