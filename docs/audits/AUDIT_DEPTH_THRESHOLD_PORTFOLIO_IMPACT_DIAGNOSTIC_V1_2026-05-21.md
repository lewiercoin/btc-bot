# AUDIT: DEPTH_THRESHOLD_PORTFOLIO_IMPACT_DIAGNOSTIC_V1
Date: 2026-05-21
Auditor: Claude Code
Commit: f0a8566

## Verdict: DONE

## Layer Separation: PASS
- Research Lab diagnostic only (research_lab/depth_threshold_portfolio_impact_diagnostic.py)
- No imports from core, execution, orchestrator, main, storage
- No sidecar changes
- No systemd changes
- Uses backtest/, research_lab/, settings modules only (allowed for research)

## Contract Compliance: PASS
- Follows hypothesis card depth_threshold_portfolio_impact_diagnostic
- Three scenarios: both_frozen (0.00649/0.00649), current_shadow (0.0075/0.00649), candidate (0.0075/0.0075)
- BTC frozen at trial-00095 across all scenarios
- All non-depth trial-00095 params frozen
- OOS window only: 2025-01-01 to 2026-03-28
- Portfolio gate applied (ResearchPortfolioGate)
- Risk caps: BTC/ETH 0.35%, SOL 0.15%

## Determinism: PASS
- Fixed scenario grid (3 scenarios, depth-only)
- Correlation matrix: deterministic Pearson calculation
- Same-bar overlap: deterministic 15m floor + set intersection
- Gates deterministic: threshold comparison, retention ratio
- Verdict deterministic: all gates + ER comparison

## State Integrity: PASS
- Source DBs read-only (BTC/ETH/SOL research snapshots)
- Replay temp DBs created/destroyed per run
- No production DB writes
- No runtime settings mutations

## Error Handling: PASS
- Gates enforced (min portfolio trades, SOL retention, max DD, max corr, max overlap)
- Builder verdict blocks promotion when gates fail
- Verdict function explicit: ASSET_SPECIFIC_DEPTH_SUPPORTED_FOR_SHADOW_DECISION vs KEEP_CURRENT_SHADOW_PROFILE_PENDING_FORWARD_EVIDENCE

## Smoke Coverage: PASS
- 6 focused tests in test_depth_threshold_portfolio_impact_diagnostic.py:
  - test_scenario_grid_keeps_current_shadow_profile_explicit
  - test_correlation_matrix_zero_fills_inactive_days
  - test_same_bar_overlap_by_pair_counts_15m_collisions
  - test_verdict_supports_asset_specific_when_frequency_and_portfolio_pass
  - test_verdict_keeps_current_profile_when_sol_retention_fails
  - test_depth_threshold_hypothesis_spec_is_valid
- Key scenarios covered: grid structure, correlation, overlap, verdict logic, hypothesis validity

## Tech Debt: LOW
- Clean implementation, no NotImplementedError stubs
- Reuses portfolio_replay_harness and multi_asset_full_pipeline_replay infrastructure
- Diagnostic-focused: clear gates, explicit verdict

## AGENTS.md Compliance: PASS
- Commit discipline: WHAT/WHY/STATUS in commit message
- No self-audit by builder (Codex correctly deferred to Claude Code)
- Scope purity: Research Lab only, no runtime/sidecar/M4 changes

## Methodology Integrity: PASS
- Diagnostic-only scope, no training or optimization
- OOS window comparison (2025-01-01 to 2026-03-28)
- Fixed scenario grid predeclared before results
- Gates enforce portfolio quality (frequency, retention, DD, correlation, overlap)
- Verdict avoids PAPER/LIVE approval (diagnostic support only)

## Promotion Safety: PASS
- Diagnostic-only checkpoint, no deployment
- Builder verdict: ASSET_SPECIFIC_DEPTH_SUPPORTED_FOR_SHADOW_DECISION (shadow decision support, not PAPER approval)
- Hypothesis out_of_scope includes: runtime deployment, sidecar changes, PAPER/LIVE orders
- No production DB writes
- Explicit interpretation: "This is not PAPER approval"

## Reproducibility & Lineage: PASS
- Hypothesis card: depth_threshold_portfolio_impact_diagnostic (ACTIVE)
- Fixed scenario grid: (0.00649/0.00649), (0.0075/0.00649), (0.0075/0.0075)
- OOS window: 2025-01-01 to 2026-03-28
- Source DBs: BTC/ETH/SOL research snapshots (audited)
- Analysis report: docs/analysis/DEPTH_THRESHOLD_PORTFOLIO_IMPACT_DIAGNOSTIC_2026-05-21.md

## Data Isolation: PASS
- Source DBs: BTC/ETH/SOL research snapshots (read-only)
- Replay temp DBs: created per symbol, destroyed after
- No production DB reads or writes
- No cross-contamination with runtime

## Search Space Governance: PASS
- Scenario grid predeclared and fixed (3 scenarios)
- Depth-only: ETH/SOL min_sweep_depth_pct [0.00649, 0.0075]
- BTC frozen at trial-00095 (0.00649)
- All other trial-00095 params frozen
- No post-hoc scenario expansion

## Artifact Consistency: PASS
- Hypothesis card, analysis report, test expectations all consistent
- Scenario results match report
- Gates results match report (all PASS)
- Builder verdict matches gate evaluation

## Boundary Coupling: PASS
- Research Lab depends only on backtest/, research_lab/, settings modules
- No coupling to core/runtime/execution/sidecar
- Reuses portfolio_replay_harness and multi_asset_full_pipeline_replay (acceptable research context)

## Critical Issues (must fix before next milestone)
None.

## Warnings (fix soon)
None.

## Observations (non-blocking)
1. Candidate asset-specific profile (ETH 0.0075, SOL 0.0075) shows exceptional portfolio improvement
2. Portfolio metrics comparison (current shadow vs candidate):
   - Trades: 303 → 267 (-11.9%, acceptable frequency reduction)
   - ER: 2.048 → 2.364 (+15.4%)
   - PF: 3.70 → 4.38 (+18.3%)
   - Max DD: 16.47R → 8.77R (-46.8%, exceptional drawdown control)
3. SOL standalone retention: 156/213 = 73.2% (well above 65% gate)
4. All 5 gates PASS for candidate scenario
5. Daily correlation remains low: max 0.199 (well below 0.70 threshold)
6. Same-bar overlap remains low: max 3.1% (well below 10% threshold)
7. SOL threshold change removes 57 standalone trades but portfolio quality improves
8. Portfolio DD improvement (46.8% reduction) is the most significant benefit
9. Asset-specific thresholds (0.0075) appear optimal for both ETH and SOL microstructure
10. BTC remains at baseline 0.00649 (no evidence yet that BTC benefits from looser threshold)

## 6-Point Diagnostic Verification

| # | Point | Status |
|---|---|---|
| 1 | Diagnostic-only scope, no runtime/sidecar/M4/PAPER/LIVE changes | ✓ PASS |
| 2 | Fixed scenario grid: depth-only ETH/SOL [0.00649, 0.0075], BTC frozen | ✓ PASS |
| 3 | OOS-only comparison (2025-01-01 to 2026-03-28) | ✓ PASS |
| 4 | Portfolio gate applied (ResearchPortfolioGate) | ✓ PASS |
| 5 | Gates enforce portfolio quality (frequency, retention, DD, corr, overlap) | ✓ PASS |
| 6 | Verdict avoids PAPER/LIVE approval (shadow decision support only) | ✓ PASS |

## Recommended Next Step

**Portfolio diagnostic is complete and supports asset-specific depth migration.**

Candidate profile: ETH 0.0075, SOL 0.0075 (BTC remains 0.00649)
- Portfolio trades: 267 (vs 303 current, -11.9%)
- Portfolio ER: 2.364 (vs 2.048 current, +15.4%)
- Portfolio PF: 4.38 (vs 3.70 current, +18.3%)
- Portfolio DD: 8.77R (vs 16.47R current, -46.8%)
- SOL retention: 73.2% (above 65% gate)
- All gates: PASS

**Key finding:** Asset-specific depth thresholds improve portfolio quality significantly, with exceptional drawdown control (46.8% reduction).

Promotion decision required:
**Option A (incremental):** Promote SOL depth to shadow immediately. Create `SOL_SHADOW_DEPTH_PARAMETER_UPDATE_V1` (mirror ETH shadow update pattern), audit, pull. Complete asset-specific depth migration for all shadow assets (BTC 0.00649, ETH 0.0075, SOL 0.0075).

**Option B (batched):** Wait to batch SOL shadow update with future multi-asset runtime promotion (PAPER/LIVE).

**Option C (deferred):** Accumulate more forward evidence on current shadow profile (ETH 0.0075, SOL 0.00649) before changing SOL.

**Recommendation:** Option A. Diagnostic strongly supports SOL 0.0075. Portfolio DD improvement (46.8%) is exceptional. SOL retention (73.2%) exceeds gate (65%) with margin. All gates PASS. Complete asset-specific depth migration now rather than waiting for runtime promotion (which may be months away pending M4 checkpoint and other dependencies).

**If Option A chosen, next milestone:**
`SOL_SHADOW_DEPTH_PARAMETER_UPDATE_V1` - update SOL shadow config from 0.00649 to 0.0075, leaving BTC/ETH unchanged. Same pattern as ETH_SHADOW_DEPTH_PARAMETER_UPDATE_V1. Code-only, audit, pull.

No immediate action required. This is a diagnostic checkpoint, not a deployment approval. User decision required for promotion path.
