# AUDIT: OPTUNA-INFRASTRUCTURE-V3-HARDENING
Date: 2026-05-07
Auditor: Claude Code
Builder: Codex
Commit: 929b737ab047df986e05d0f599c6e8d6681b06c3
Branch: claude/audit-wf-light-protocol-ZXDA9

## Verdict: DONE

## Layer Separation: PASS
## Contract Compliance: PASS
## Determinism: PASS
## State Integrity: PASS
## Error Handling: PASS
## Smoke Coverage: PASS
## Tech Debt: LOW
## AGENTS.md Compliance: PASS
## Methodology Integrity: PASS
## Promotion Safety: PASS
## Reproducibility & Lineage: PASS
## Data Isolation: PASS
## Search Space Governance: PASS
## Artifact Consistency: PASS
## Boundary Coupling: PASS

---

## Audit Summary

V3 infrastructure hardening addresses 6 Campaign V2 operational gaps with production-grade implementations. All changes are backward-compatible, deterministic, and well-tested. Raw vs objective metrics separation provides audit trail for TPE transforms. WF-winners-only warm-start mode eliminates cold-start risk from unvalidated history. Multivariate TPE auto-disable prevents RandomSampler fallback storms. Trial metadata is comprehensive for lineage tracking. V3 range tightening is evidence-based and conservative. Drawdown unit alignment removes protocol ambiguity.

**No blockers for Campaign V3 launch.**

---

## Changes Delivered

### 1. Raw vs Objective Metrics Separation
- **What**: Added `raw_metrics_json` and `objective_metrics_json` columns to trials table
- **Why**: Campaign V2 stored only post-transform metrics, making it impossible to audit what TPE actually saw vs what the backtest produced
- **Implementation**:
  - `raw_metrics_json` stores backtest output before caps/penalties/rejections
  - `objective_metrics_json` stores transformed metrics returned to Optuna
  - `metrics_json` kept for backward compatibility (now aliases `raw_metrics_json`)
  - `ObjectiveMetrics` added to `TrialEvaluation` dataclass as optional field
  - `_objective_metrics_from_raw()` helper constructs objective metrics
- **Audit trail**: Trial store can now answer "did TPE see raw PF=12.0 or capped PF=5.0?"

### 2. WF-Winners-Only Warm-Start Mode
- **What**: New `--warm-start-mode={all|wf-winners-only}` with production default `wf-winners-only`
- **Why**: Campaign V2 warm-started from all historical trials, including those that never passed walk-forward validation
- **Implementation**:
  - `load_walkforward_passed_candidate_ids()` queries walkforward_reports table for `passed=True` trials
  - `_enqueue_warm_start_trials()` filters to WF-passed trials when mode is `wf-winners-only`
  - CLI plumbing in `research_lab/cli.py`
  - Study attr `warm_start_mode` documents which mode was used
- **Safety**: V3 campaigns start from validated candidates only, not screening-grade trials

### 3. Multivariate TPE Auto-Disable Policy
- **What**: Auto-disable `multivariate=True` when dynamic-bound params are active
- **Why**: Optuna's multivariate TPE falls back to RandomSampler for conditional distributions (e.g., `ema_slow > ema_fast + 1`), causing gradient loss
- **Implementation**:
  - `_DYNAMIC_BOUND_PARAMS = frozenset(("ema_slow", "tp2_atr_mult", "high_vol_leverage"))`
  - `_resolve_multivariate_tpe_policy()` checks active search space for dynamic params
  - Returns `(False, "disabled_dynamic_bounds:tp2_atr_mult,high_vol_leverage")` if conflict detected
  - Study and trial attrs document: `multivariate_tpe_requested`, `multivariate_tpe_effective`, `multivariate_tpe_policy`
  - Warning logged when requested but auto-disabled
- **Correctness**: Preserves ordinary TPE behavior instead of degrading to random search

### 4. Richer Optuna Trial Metadata
- **What**: 14 new trial user attributes for lineage and diagnostics
- **Implementation**:
  - Protocol: `protocol_hash`, `baseline_version`, `config_hash` (alias)
  - Search space: `search_space_signature`, `trial_context_signature`
  - Date range: `date_range_start`, `date_range_end`
  - Sampler: `multivariate_tpe_requested`, `multivariate_tpe_effective`, `multivariate_tpe_policy`
  - Warm-start: `warm_start_mode`
  - Objective: `objective_expectancy_r`, `objective_profit_factor`, `objective_max_drawdown_pct`
  - Performance: `trial_wall_time_sec`, `trial_wall_time_s`
  - Rejection: `rejection_reason` (already existed, now always populated)
- **Value**: Trial metadata is self-contained for Optuna UI inspection and post-campaign analysis

### 5. Conservative V3 Range Tightening
- **What**: 7 parameter high bounds tightened based on Campaign V2 accepted vs rejected trial evidence
- **Evidence**: `docs/analysis/OPTUNA_V3_RANGE_TIGHTENING_2026-05-07.md`
  - `compression_atr_norm_max`: 0.05 → 0.02 (accepted p90=0.0170, rejected p90=0.0253)
  - `post_liq_tfi_abs_min`: 1.00 → 0.85 (accepted p90=0.77, rejected p90=0.83)
  - `min_sweep_depth_pct`: 0.0200 → 0.0100 (accepted p90=0.00825, rejected p75=0.01081)
  - `entry_offset_atr`: 2.00 → 0.80 (accepted p90=0.55, rejected p90=0.69)
  - `min_stop_distance_pct`: 0.0200 → 0.0100 (accepted p90=0.0059, rejected p90=0.0081)
  - `risk_per_trade_pct`: 0.0500 → 0.0200 (accepted p90=0.0155, rejected p90=0.0180)
  - `trailing_atr_mult`: 5.0 → 4.0 (accepted p90=2.9, rejected p90=3.6)
- **Rationale**: Accepted trials sat well below old upper bound; rejected trials concentrated in high tail
- **Conservative**: Does NOT tighten ranges just because Optuna rarely visited them; only when rejected trials cluster at high end
- **Documentation**: Inline rationale dict `_V3_RANGE_TIGHTENING_RATIONALE` in `param_registry.py`

### 6. Drawdown Unit Alignment
- **What**: `default_protocol.json` now documents that `max_drawdown_pct_per_window: 0.5` means 50% drawdown (fraction units)
- **Why**: Protocol used percentage-like naming but code expected fraction units; ambiguous for operators
- **Implementation**: Test `test_walkforward_drawdown_gate_uses_fraction_units()` validates 0.5 → "50%" interpretation
- **Smoke test**: `_segment_failures()` correctly rejects `max_drawdown_pct=0.55` when threshold is `0.50`

---

## Layer Separation — PASS

All changes isolated to `research_lab/`:
- `experiment_store.py`: trial persistence (raw/objective columns, WF-passed query)
- `integrations/optuna_driver.py`: Optuna integration (multivariate policy, warm-start filtering, trial metadata)
- `param_registry.py`: search space config (V3 range tightening)
- `cli.py`: CLI plumbing (`--warm-start-mode`)
- `types.py`: added `objective_metrics: ObjectiveMetrics | None` to `TrialEvaluation`

Zero imports from `core/`, `execution/`, `risk/`, `governance/`, `data/`.

Blueprint updated: `BLUEPRINT_RESEARCH_LAB.md` section "Optuna Infrastructure Policy" documents V3 hardening.

Milestone tracker updated: `MILESTONE_TRACKER.md` shows OPTUNA-INFRASTRUCTURE-V3-HARDENING as active.

---

## Contract Compliance — PASS

`TrialEvaluation` contract extended cleanly:
- Added `objective_metrics: ObjectiveMetrics | None = None`
- Backward compatible: existing trials with `objective_metrics=None` still load correctly
- `_parse_trial_row()` handles missing `objective_metrics_json` column gracefully

`experiment_store.py` table schema migration:
- `_ensure_trial_metric_columns()` adds `raw_metrics_json` and `objective_metrics_json` columns if missing
- Uses `ALTER TABLE ... ADD COLUMN ... NULL` for backward compatibility
- Migration runs automatically on `init_store()`

Walk-forward contract unchanged. Warm-start filtering is additive (new mode option, not a breaking change).

---

## Determinism — PASS

All changes are deterministic:
- Raw/objective metrics separation: deterministic transform (caps/penalties are fixed formulas)
- WF-winners-only filtering: deterministic query (`passed=True` in walkforward_reports)
- Multivariate TPE policy: deterministic resolution (checks active search space against `_DYNAMIC_BOUND_PARAMS`)
- V3 range tightening: deterministic search space (fixed bounds)
- Trial metadata: deterministic capture (all fields derived from config or backtest output)

No hidden state, no time-dependent behavior, no random seeds changed.

Smoke test `test_multivariate_tpe_auto_disables_for_dynamic_bounds()` validates policy is deterministic.

---

## State Integrity — PASS

Trial store backward compatibility verified:
- Existing stores load correctly (missing columns added via `ALTER TABLE`)
- `metrics_json` aliased to `raw_metrics_json` for legacy read path
- `objective_metrics` is optional; trials without it still parse

Walk-forward store unchanged (no schema changes).

Warm-start filtering is read-only (queries existing WF reports, does not mutate).

No migration script needed — schema evolution is automatic via `_ensure_*` helpers.

---

## Error Handling — PASS

Multivariate TPE policy:
- Warning logged when requested but auto-disabled: "Multivariate TPE requested but disabled for this search space: disabled_dynamic_bounds:tp2_atr_mult"
- Study attrs document effective vs requested state for post-campaign diagnosis

Warm-start mode validation:
- `ValueError` raised for unsupported mode: `if warm_start_mode not in {WARM_START_MODE_ALL, WARM_START_MODE_WF_WINNERS_ONLY}`
- CLI uses `choices=("all", "wf-winners-only")` to prevent typos

Trial metadata capture:
- All attrs populated even on rejection paths
- `rejection_reason` always set when trial is rejected
- `constraint_violations` attr set to `[1.0]` for hard rejections (Optuna infeasibility signal)

---

## Smoke Coverage — PASS

6 new tests added to `test_research_lab_smoke.py`:
1. `test_warm_start_wf_winners_only_filters_to_passing_walkforward_trials()` — WF-winners-only mode
2. `test_multivariate_tpe_auto_disables_for_dynamic_bounds()` — multivariate policy
3. `test_walkforward_drawdown_gate_uses_fraction_units()` — drawdown unit alignment
4. `test_trial_store_persists_raw_and_objective_metrics()` — raw/objective persistence
5. Updated `test_run_optuna_study_hard_blocks_trials_below_80_trades()` — validates objective_metrics on rejection
6. Updated `test_run_optuna_study_hard_blocks_artifact_metrics()` — validates artifact block produces objective_metrics

Test results: **40 passed, 2 skipped** (skips are intentional for 8f2c6f2 baseline features)

Skipped tests:
- `test_autoresearch_grid_respects_commit_8f2c6f2_baseline()` — level_min_age_bars not in 8f2c6f2
- `test_autoresearch_loop_single_pass_produces_ranked_loop_report()` — level_min_age_bars not in 8f2c6f2

Builder validation:
- Research Lab smoke: 40/42 passed
- Full suite: 311/335 passed, 24 skipped
- `compileall research_lab/ tests/test_research_lab_smoke.py`: PASS
- 10-trial synthetic Optuna campaign: PASS (multivariate_tpe_effective=false, policy documented)

---

## Tech Debt — LOW

**D18 (sweep-rate threshold) remains open** — not addressed by this milestone, correctly deferred to post-Campaign V2 analysis.

**No new debt introduced.**

Minor: `trial_wall_time_s` is duplicate of `trial_wall_time_sec` — both attrs set for compatibility. Acceptable.

Minor: `config_hash` trial attr is alias for `baseline_version` — both set for Optuna UI compatibility. Acceptable.

---

## AGENTS.md Compliance — PASS

Commit message follows discipline:
- WHAT: lists 5 deliverables
- WHY: explains Campaign V2 gaps and V3 production requirements
- STATUS: builder checkpoint ready for audit, validation summary included

Commit is atomic (all V3 infrastructure changes in single commit, no mixed scope).

No self-approval by Codex — commit message correctly says "Pending: Claude Code audit after push".

Branch `claude/audit-wf-light-protocol-ZXDA9` is consistent with milestone workflow.

---

## Methodology Integrity — PASS

Raw vs objective metrics separation ensures honest audit trail:
- Research lab can now prove what Optuna saw vs what backtest produced
- Campaign reports can show "trial-00042 had raw PF=12.0 but objective PF=5.0 due to anti-overfitting cap"
- No methodology claims changed — separation is infrastructure only

WF-winners-only mode does NOT bypass validation:
- Still requires explicit walk-forward pass to be included in warm-start
- Does NOT lower promotion standards
- Production default is safer (cold-start from validated trials only)

V3 range tightening is evidence-based:
- All changes documented with V2 accepted/rejected percentile evidence
- Does NOT claim tightening improves strategy quality
- Conservative: only tightens high tails where rejected trials clustered

Blueprint updated with honest V3 hardening summary (no methodology expansion claims).

---

## Promotion Safety — PASS

WF-winners-only mode hardens promotion pipeline:
- V3 campaigns will NOT warm-start from screening-grade trials
- Only trials with `passed=True` in walkforward_reports are included
- Hard gate: if no WF-passed trials exist, only baseline config is enqueued

Multivariate TPE auto-disable prevents gradient loss:
- Conditional distributions now use ordinary TPE instead of RandomSampler fallback
- Increases probability of finding credible candidates

Raw/objective metrics separation improves promotion audit:
- Reviewers can verify objective transforms were applied correctly
- Trial-00042 with raw PF=351B and objective PF=0.1 is now auditable

V3 range tightening reduces low-confidence tail exploration:
- Campaign V3 will spend fewer trials on parameter regions that V2 rejected
- Does NOT bypass promotion standards — only narrows search space

No promotion policy changes in this milestone.

---

## Reproducibility & Lineage — PASS

Trial lineage now complete:
- `protocol_hash`, `search_space_signature`, `regime_signature`, `trial_context_signature`, `baseline_version` all persisted
- `date_range_start`, `date_range_end` document temporal scope
- `multivariate_tpe_effective` and `multivariate_tpe_policy` document sampler config
- `warm_start_mode` documents which warm-start filter was used
- `raw_metrics_json` and `objective_metrics_json` provide full transform audit trail

V3 range tightening evidence committed:
- `docs/analysis/OPTUNA_V3_RANGE_TIGHTENING_2026-05-07.md` documents V2 percentile evidence
- Inline rationale dict `_V3_RANGE_TIGHTENING_RATIONALE` in `param_registry.py`

Blueprint updated with V3 infrastructure policy section.

Commit SHA not yet persisted in experiment store (known limitation, tracked as future work).

---

## Data Isolation — PASS

All changes are read-only with respect to source DB:
- Warm-start filtering queries experiment store only (no source DB access)
- Trial persistence writes to experiment store only
- V3 range tightening changes search space config (no data layer changes)

Walk-forward reports table is read-only for warm-start filtering.

No snapshot DB changes.

---

## Search Space Governance — PASS

V3 range tightening follows governance policy:
- 7 params moved from ACTIVE with old bounds to ACTIVE with new bounds
- No params moved between ACTIVE/FROZEN/DEFERRED/UNSUPPORTED
- All changes documented with V2 evidence
- Inline rationale preserved in `_V3_RANGE_TIGHTENING_RATIONALE` dict

`_FROZEN_REASONS` and `_DEFERRED_REASONS` unchanged.

Multivariate TPE policy does NOT change param status:
- `_DYNAMIC_BOUND_PARAMS` is a sampler policy constant, not a param status change
- Dynamic-bound params (`ema_slow`, `tp2_atr_mult`, `high_vol_leverage`) remain ACTIVE

Blueprint section "Optuna Infrastructure Policy" documents multivariate policy and V3 range tightening.

---

## Artifact Consistency — PASS

Trial artifacts are backward-compatible:
- Existing trial stores load correctly (schema migration via `ALTER TABLE`)
- New trials have `raw_metrics_json` and `objective_metrics_json` columns populated
- Legacy trials have `raw_metrics_json=NULL` and `objective_metrics_json=NULL` — parse correctly

Walk-forward artifacts unchanged (no schema changes).

Warm-start filtering reads existing WF reports (no new artifact format).

V3 range evidence artifact committed: `docs/analysis/OPTUNA_V3_RANGE_TIGHTENING_2026-05-07.md`.

---

## Boundary Coupling — PASS

All changes isolated to research lab:
- Zero coupling to live bot (`core/`, `execution/`, `orchestrator.py` unchanged)
- Zero coupling to dashboard (`dashboard/` unchanged)
- Zero coupling to data collectors (`data/` unchanged)

`settings.py` unchanged (V3 range tightening uses `param_registry.py` overrides, not dataclass defaults).

Backtest runner unchanged (raw/objective metrics split happens in Optuna driver, not backtest layer).

---

## Critical Issues

**None.**

---

## Warnings

**None.**

---

## Observations (non-blocking)

1. **Trial metadata duplication**: `trial_wall_time_sec` and `trial_wall_time_s` both set to same value. Acceptable for Optuna UI compatibility but redundant.

2. **Config hash aliasing**: `config_hash` trial attr is alias for `baseline_version`. Both set for compatibility. Acceptable.

3. **V3 range tightening is conservative**: Only 7 params tightened despite Campaign V2 having 85 accepted trials. Many params have unused high-bound tail but were NOT tightened. This is correct discipline — tighten only when evidence shows rejected trial concentration in high tail.

4. **Smoke test coverage for range tightening is indirect**: `test_param_registry_frozen_params_are_correct()` validates new high bounds but does NOT validate V2 evidence percentiles. Evidence doc `OPTUNA_V3_RANGE_TIGHTENING_2026-05-07.md` is source of truth. Acceptable — range tightening is policy decision, not algorithmic correctness.

5. **Multivariate TPE policy is static**: `_DYNAMIC_BOUND_PARAMS` is hardcoded frozenset. If future params have dynamic bounds (e.g., `tp3_atr_mult > tp2_atr_mult`), they must be added manually. Acceptable — dynamic bounds are rare and should be explicit policy decisions.

---

## Tracked Debt

No new debt introduced. D18 (sweep-rate threshold validation) remains open, correctly deferred to post-Campaign V2 analysis per prior milestone.

---

## Recommended Next Step

**Launch Campaign V3 with V3 infrastructure hardening.**

No blockers. All axes PASS. Tests pass 40/42 (2 intentional skips). Builder validation confirms 10-trial synthetic campaign works with new infrastructure.

**Campaign V3 launch command (reference):**
```bash
cd /home/btc-bot/btc-bot
nohup .venv/bin/python -m research_lab optimize \
  --start-date 2022-01-01 --end-date 2026-03-28 \
  --study-name optuna-default-v3 --n-trials 350 --seed 44 \
  --warm-start-from-store --warm-start-mode wf-winners-only \
  --multivariate-tpe \
  --max-sweep-rate 0.60 \
  --optuna-storage-path /home/btc-bot/btc-bot/research_lab/optuna_default_v3.db \
  > /tmp/optuna_v3.log 2>&1 &
```

**Before V3 launch:**
1. Update `MILESTONE_TRACKER.md`: mark OPTUNA-INFRASTRUCTURE-V3-HARDENING DONE, open OPTUNA-CAMPAIGN-V3
2. Push this audit to remote
3. User approval for V3 launch

**Parallel (not blocking V3):**
- trial-00000 from Campaign V1 remains the only clean paper trading candidate
- User can decide: launch V3 first, or deploy trial-00000 to paper trading now
