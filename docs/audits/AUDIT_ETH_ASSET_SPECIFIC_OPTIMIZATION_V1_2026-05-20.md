# AUDIT: ETH_ASSET_SPECIFIC_OPTIMIZATION_V1
Date: 2026-05-20
Auditor: Claude Code
Commit: 7755272

## Verdict: DONE

## Layer Separation: PASS
- Research Lab offline only (research_lab/eth_asset_specific_optimization.py)
- No imports from core, execution, orchestrator, main, storage
- No sidecar changes (shadow_orchestrator.py, shadow_signal_cycle.py, sidecar_main.py unchanged)
- No systemd changes
- Uses backtest/, research_lab/, settings modules only (allowed for research)

## Contract Compliance: PASS
- Follows hypothesis card eth_asset_specific_optimization_v1
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
- Research snapshot read-only (DEFAULT_ETH_DB)
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
  - 7 tests in test_eth_asset_specific_optimization.py
  - 6 tests in test_eth_trial_00095_transfer_feasibility.py
- Key tests:
  - test_predeclared_grid_is_fixed_and_contains_baseline_point
  - test_train_passes_requires_all_train_gates
  - test_train_score_rewards_er_and_penalizes_drawdown
  - test_oos_gates_require_improvement_over_baseline_and_cost_robustness
  - test_builder_verdict_blocks_when_any_oos_gate_fails
  - test_eth_asset_specific_hypothesis_spec_is_valid

## Tech Debt: LOW
- Grid small by design (3 variants, coarse depth-only)
- No NotImplementedError stubs
- Reuses ETH transfer infrastructure (fold_windows, load_trial_params, etc.)

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
- Builder verdict: ETH_ASSET_SPECIFIC_CANDIDATE_FOR_AUDIT (not approved for runtime)
- Hypothesis out_of_scope includes: runtime deployment, sidecar changes, M4 changes, BTC/SOL changes
- No PAPER/LIVE orders
- No production DB writes

## Reproducibility & Lineage: PASS
- Hypothesis card: eth_asset_specific_optimization_v1 (ACTIVE)
- Fixed grid: min_sweep_depth_pct [0.0055, 0.00649, 0.0075]
- Train window: 2022-01-01 to 2025-01-01
- OOS window: 2025-01-01 to 2026-03-28
- Selected variant: ETH_OPT_D0.00750 (min_sweep_depth_pct = 0.0075)
- Analysis report: docs/analysis/ETH_ASSET_SPECIFIC_OPTIMIZATION_2026-05-20.md
- Cache: research_lab/snapshots/eth_asset_specific_optimization_v1_cache.json

## Data Isolation: PASS
- Source DB: research_lab/data/eth_research_2022_2026_v1.db (read-only)
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
- Selected variant ETH_OPT_D0.00750 matches analysis report
- OOS gates results match report (all gates PASS)
- WF folds results match report (4/4 positive)
- 2x cost results match report (ER 1.808)

## Boundary Coupling: PASS
- Research Lab depends only on backtest/, research_lab/, settings modules
- No coupling to core/runtime/execution/sidecar
- Reuses ETH transfer infrastructure (acceptable research context)

## Critical Issues (must fix before next milestone)
None.

## Warnings (fix soon)
None.

## Observations (non-blocking)
1. Selected variant looser threshold (0.0075 vs 0.00649) improves ETH performance
2. Baseline (D0.00649 frozen transfer): 162 trades, ER 1.766, PF 2.73
3. Selected (D0.00750): 127 trades, ER 2.190, PF 3.50 (+24% ER, +28% PF)
4. Tighter threshold (D0.00550) degrades: 235 trades, ER 1.604, PF 2.47
5. WF consistency: all 4 yearly folds positive (ER 2.248, 2.423, 2.412, 2.190)
6. 2x cost robustness: ER 1.808 (well above 1.0 gate)
7. ETH microstructure appears to support slightly looser sweep depth vs BTC
8. Trade count reduction (162 → 127) acceptable given ER/PF improvement

## 8-Point Research Methodology Verification

| # | Point | Status |
|---|---|---|
| 1 | Research-only scope, no runtime/sidecar/M4 contamination | ✓ PASS |
| 2 | Fixed depth-only grid: min_sweep_depth_pct [0.0055, 0.00649, 0.0075] | ✓ PASS |
| 3 | All non-depth trial-00095 params frozen | ✓ PASS |
| 4 | Train-only selection: 2022-01-01 to 2025-01-01 | ✓ PASS |
| 5 | OOS evaluation untouched: 2025-01-01 to 2026-03-28 | ✓ PASS |
| 6 | Selected variant ETH_OPT_D0.00750 supported by OOS gates (all PASS) | ✓ PASS |
| 7 | 2x cost (ER 1.808) and 4/4 WF fold gates correctly applied | ✓ PASS |
| 8 | No parameter promotion implied (builder verdict: candidate for audit) | ✓ PASS |

## Recommended Next Step

**ETH depth optimization is research-complete and audit-approved.**

Selected variant: ETH_OPT_D0.00750 (min_sweep_depth_pct = 0.0075)
- Train: 269 trades, ER 2.288, PF 3.93, DD 5.61%
- OOS: 127 trades, ER 2.190, PF 3.50, DD 4.88%
- Improvement vs baseline: ER +24.0%, PF +28.3%
- Cost robustness: 2x cost ER 1.808 (PASS)
- WF consistency: 4/4 positive folds (PASS)

Promotion decision required:
**Option A (conservative):** Wait for SOL depth optimization to complete. Batch promote BTC (frozen trial-00095), ETH (D0.00750), SOL (TBD) together in one multi-asset deployment milestone.

**Option B (incremental):** Promote ETH depth optimization to sidecar first (shadow_no_orders), collect multi-asset shadow evidence, then decide on full multi-asset runtime promotion later.

**Option C (deferred):** Keep ETH at frozen trial-00095 transfer for now. Revisit ETH depth optimization after SOL shadow evidence collection completes.

No immediate action required. This is a research checkpoint, not a deployment approval. User decision required for promotion path.
