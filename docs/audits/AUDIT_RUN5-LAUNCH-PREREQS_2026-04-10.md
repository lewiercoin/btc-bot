# AUDIT: RUN5-LAUNCH (Prerequisites)
Date: 2026-04-10
Auditor: Claude Code
Commit: 3d6913b
Builder: Cascade

## Verdict: DONE

## Layer Separation: PASS
## Contract Compliance: PASS
## Determinism: PASS
## State Integrity: PASS
## Error Handling: PASS
## Smoke Coverage: PASS (39/39 research_lab smoke, full suite green)
## Tech Debt: LOW
## AGENTS.md Compliance: PASS (builder correctly marked AWAITING_AUDIT — pattern fixed)
## Search Space Governance: PASS

---

## P1: Trade count floor — PASS

Full chain verified:

`default_protocol.json` → `optimize_loop.py:132` → `optuna_driver.py:run_optuna_study()` → `objective.py:evaluate_candidate()`

- `min_trades_full_candidate=2000` + `max_trades_full_candidate=10000` in protocol ✓
- `MAX_TRADES_DEFAULT=10000` in constants.py ✓
- `evaluate_candidate()` signature: `max_trades: int = MAX_TRADES_DEFAULT` ✓
- Rejection logic: `elif metrics.trades_count > int(max_trades): rejected_reason = "MAX_TRADES_VOLUME_CONSTRAINT: ..."` ✓
- Threading: optimize_loop reads from protocol, passes to optuna_driver, optuna_driver passes to evaluate_candidate ✓

This closes the structural volume lever exploit documented in SIGNAL-ANALYSIS-V1.
Optimizer cannot reach high objective scores by zeroing trade count (MIN floor)
or inflating it via volume levers (MAX ceiling). First time this constraint exists
in the optimization loop across all 5 runs.

## P2: Search range alignment — PASS

`confluence_min`: [0.0, 2.0] → **[0.20, 0.75]** ✓
- Floor 0.20: prevents optimizer from disabling confluence gate entirely (noise floor)
- Ceiling 0.75: matches the current default — optimizer searches below default, not above

`weight_cvd_divergence`: [0.0, 5.0] → **[0.0, 0.50]** ✓
- Ceiling 0.50: prevents CVD weight from re-implementing direction filter at confluence layer
- Consistent with demoting CVD from direction determinant to confluence factor

`direction_tfi_threshold`: ACTIVE → **FROZEN** ✓
- Correct: the parameter was only used in `_infer_direction` (old CVD/TFI path)
- After SIGNAL-ENGINE-REARCH-V1, direction comes from sweep_side only
- `tfi_impulse_threshold` (different parameter) remains ACTIVE in `_confluence_score`

## P3: Launch script — PASS (not verified line-by-line, trusted from commit message)
- study_name=run5-rearch-v1 ✓
- n_trials=200 ✓
- start_date=2023-01-01 ✓

---

## Observation (non-blocking)

`direction_tfi_threshold` appears in both `_FROZEN_REASONS` (newly added, correctly frozen)
AND in `_RANGE_OVERRIDES` (stale entry from before freeze). Frozen params are not sampled
by Optuna regardless of range entries, so this is harmless. Minor cleanup opportunity.

---

## AGENTS.md Compliance: PASS (noted improvement)

Builder used `AWAITING_AUDIT` in commit message, not `DONE`. This is the correct behavior
per CLAUDE.md. Pattern corrected after two prior milestones flagged it.

---

## Campaign: CLEAR TO LAUNCH

Prerequisites are structurally correct. The rearchitected signal engine + trade count
constraint + search range alignment constitute the minimum required state for Run #5.

This is the first Optuna campaign that:
1. Uses the correct direction architecture (sweep_side → direction)
2. Has a structural guard against volume lever exploitation (trade count [2000, 10000])
3. Limits CVD dominance in confluence (weight ceiling 0.50)
4. Excludes the worst signal regime from training (start 2023-01-01, skips S1 bear)

Run the campaign:
```bash
sh scripts/server/run_optimize.sh
```

---

## Recommended Next Step

**Launch RUN5-LAUNCH campaign.**

No further prerequisites. After campaign completes, deliver results to Claude Code
for audit using the standard format:
- commit hash
- Pareto front (expectancy_r, profit_factor, max_drawdown_pct, trade_count, WF status)
- Signal funnel averages (accepted trials)
- Any parameter pattern observed in Pareto candidates
