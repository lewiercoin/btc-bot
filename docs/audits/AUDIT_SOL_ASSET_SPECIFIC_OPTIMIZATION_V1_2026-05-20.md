# AUDIT: SOL_ASSET_SPECIFIC_OPTIMIZATION_V1
Date: 2026-05-20
Auditor: Claude Code
Commit: 86740f6

## Verdict: DONE

## Layer Separation: PASS
- Research Lab offline only (research_lab/sol_asset_specific_optimization.py)
- No imports from core, execution, orchestrator, main, storage
- No sidecar changes (shadow_orchestrator.py, shadow_signal_cycle.py, sidecar_main.py unchanged)
- No systemd changes
- Uses backtest/, research_lab/, settings modules only (allowed for research)

## Contract Compliance: PASS
- Follows hypothesis card sol_asset_specific_optimization_v1
- Depth-only optimization: min_sweep_depth_pct [0.0055, 0.00649, 0.0075]
- All other trial-00095 params frozen (confluence_min, direction_tfi_threshold, etc.)
- Train-only selection: 2022-01-01 to 2025-01-01
- OOS evaluation untouched: 2025-01-01 to 2026-03-28
- Full-year walk-forward and 2x cost stress applied to selected train champion only

## Determinism: PASS
- Fixed grid: 3 variants, depth-only
- Selection deterministic: max(train_score, trades_count, variant_id)
- train_score = ER * trade_quality - DD * 5.0 (deterministic formula)
- No random sampling, no post-hoc rescue

## State Integrity: PASS
- Research snapshot read-only (DEFAULT_SOL_DB)
- Replay temp DB created/destroyed per run (tempfile)
- No production DB writes
- No runtime settings mutations

## Error Handling: PASS
- Train gates enforced (min trades, ER, PF, max DD)
- OOS gates enforced (min trades, ER, PF, max DD, improvement, cost robustness, WF folds)
- Builder verdict blocks promotion when any OOS gate fails
- Missing data handled (variant evaluation skipped if backtest fails)

## Smoke Coverage: PASS
- 13 tests pass:
  - 7 tests in test_sol_asset_specific_optimization.py
  - 6 tests in test_sol_trial_00095_transfer_feasibility.py
- Key tests:
  - test_predeclared_grid_is_fixed_and_contains_baseline_point
  - test_train_passes_requires_all_train_gates
  - test_train_score_rewards_er_and_penalizes_drawdown
  - test_oos_gates_require_improvement_over_baseline_and_cost_robustness
  - test_builder_verdict_blocks_when_any_oos_gate_fails
  - test_sol_asset_specific_hypothesis_spec_is_valid

## Tech Debt: LOW
- Grid small by design (3 variants, coarse depth-only)
- No NotImplementedError stubs
- Reuses SOL transfer infrastructure (fold_windows, load_trial_params, etc.)

## AGENTS.md Compliance: PASS
- Commit discipline: WHAT/WHY/STATUS in commit message
- No self-audit by builder (Codex correctly deferred to Claude Code)
- Scope purity: Research Lab only, no runtime/sidecar/M4 changes

## Methodology Integrity: PASS
- Hypothesis card predeclared and fixed before results
- Train-only selection (train_score, not OOS metrics)
- OOS gates applied after selection (no peeking)
- 2x cost and WF diagnostics applied only to selected train champion
- No post-hoc rescue (if selected fails OOS, verdict = no promotion)
- Kill criteria enforced: runtime change, post-hoc rescue, source DB mutation, OOS selection all blocked

## Promotion Safety: PASS
- Research-only checkpoint, no deployment
- Builder verdict: SOL_ASSET_SPECIFIC_CANDIDATE_FOR_AUDIT (not approved for runtime)
- Hypothesis out_of_scope includes: runtime deployment, sidecar changes, M4 changes, BTC/ETH changes
- No PAPER/LIVE orders
- No production DB writes

## Reproducibility & Lineage: PASS
- Hypothesis card: sol_asset_specific_optimization_v1 (ACTIVE)
- Fixed grid: min_sweep_depth_pct [0.0055, 0.00649, 0.0075]
- Train window: 2022-01-01 to 2025-01-01
- OOS window: 2025-01-01 to 2026-03-28
- Selected variant: SOL_OPT_D0.00750 (min_sweep_depth_pct = 0.0075)
- Analysis report: docs/analysis/SOL_ASSET_SPECIFIC_OPTIMIZATION_2026-05-20.md
- Cache: research_lab/snapshots/sol_asset_specific_optimization_v1_cache.json

## Data Isolation: PASS
- Source DB: research_lab/data/sol_research_2022_2026_v1.db (read-only)
- Replay temp DB: created per run, destroyed after
- No production DB reads or writes
- No cross-contamination with BTC M4 or runtime

## Search Space Governance: PASS
- Grid predeclared and fixed (3 variants)
- Depth-only: min_sweep_depth_pct [0.0055, 0.00649, 0.0075]
- All other trial-00095 params frozen (no confluence, TFI, CVD, OI, funding, exit tuning)
- No post-hoc grid expansion

## Artifact Consistency: PASS
- Hypothesis card, analysis report, test expectations all consistent
- Selected variant SOL_OPT_D0.00750 matches analysis report
- OOS gates results match report (all gates PASS)
- WF folds results match report (4/4 positive)
- 2x cost results match report (ER 2.204)

## Boundary Coupling: PASS
- Research Lab depends only on backtest/, research_lab/, settings modules
- No coupling to core/runtime/execution/sidecar
- Reuses SOL transfer infrastructure (acceptable research context)

## Critical Issues (must fix before next milestone)
None.

## Warnings (fix soon)
None.

## Observations (non-blocking)
1. Selected variant looser threshold (0.0075 vs 0.00649) dramatically improves SOL performance
2. Baseline (D0.00649 frozen transfer): 213 trades, ER 2.041, PF 3.32, DD 7.92%
3. Selected (D0.00750): 156 trades, ER 2.573, PF 4.29, DD 3.57% (+26% ER, +29% PF, -55% DD)
4. Tighter threshold (D0.00550) fails train gates: 17.92% drawdown exceeds 15% limit
5. WF consistency: all 4 yearly folds positive (ER 2.198, 2.562, 2.839, 2.573)
6. 2x cost robustness: ER 2.204 (well above 1.0 gate)
7. SOL microstructure matches ETH: both prefer 0.0075 vs BTC baseline 0.00649
8. Trade count reduction (213 → 156) acceptable given ER/PF/DD improvement
9. Drawdown improvement is exceptional: 7.92% → 3.57%, better control than baseline
10. Only 1 of 3 variants passed train gates due to drawdown constraint (train_max_dd = 0.15)

## 8-Point Research Methodology Verification

| # | Point | Status |
|---|---|---|
| 1 | Research-only scope, no runtime/sidecar/M4 contamination | ✓ PASS |
| 2 | Fixed depth-only grid: min_sweep_depth_pct [0.0055, 0.00649, 0.0075] | ✓ PASS |
| 3 | All non-depth trial-00095 params frozen | ✓ PASS |
| 4 | Train-only selection: 2022-01-01 to 2025-01-01 | ✓ PASS |
| 5 | OOS evaluation untouched: 2025-01-01 to 2026-03-28 | ✓ PASS |
| 6 | Selected variant SOL_OPT_D0.00750 supported by OOS gates (all PASS) | ✓ PASS |
| 7 | 2x cost (ER 2.204) and 4/4 WF fold gates correctly applied | ✓ PASS |
| 8 | No parameter promotion implied (builder verdict: candidate for audit) | ✓ PASS |

## Recommended Next Step

**SOL depth optimization is research-complete and audit-approved.**

Selected variant: SOL_OPT_D0.00750 (min_sweep_depth_pct = 0.0075)
- Train: 794 trades, ER 2.546, PF 4.90, DD 6.38%
- OOS: 156 trades, ER 2.573, PF 4.29, DD 3.57%
- Improvement vs baseline: ER +26.1%, PF +29.3%, DD -54.9%
- Cost robustness: 2x cost ER 2.204 (PASS)
- WF consistency: 4/4 positive folds (PASS)

Promotion decision required:
**Option A (incremental):** Promote SOL depth optimization to sidecar (shadow_no_orders) immediately. Mirror ETH shadow update pattern: small code-only milestone (SOL_SHADOW_DEPTH_PARAMETER_UPDATE_V1), audit, pull.

**Option B (batched):** Wait to batch SOL shadow update with ETH/BTC/SOL runtime promotion when multi-asset portfolio moves beyond shadow.

**Option C (deferred):** Keep SOL at frozen trial-00095 transfer for now. Accumulate more ETH shadow evidence before adding SOL to shadow mix.

Recommended: **Option A** (immediate incremental). SOL optimization passed all gates with exceptional results. No reason to delay forward SOL shadow evidence collection while ETH shadow already active. Batching is operational convenience, not a safety requirement.

**If Option A chosen, next milestone:**
`SOL_SHADOW_DEPTH_PARAMETER_UPDATE_V1` - update SOL shadow config from 0.00649 to 0.0075, leaving BTC/ETH unchanged. Same pattern as ETH_SHADOW_DEPTH_PARAMETER_UPDATE_V1.

No immediate action required. This is a research checkpoint, not a deployment approval. User decision required for promotion path.
