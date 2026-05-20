# AUDIT: SOL_RISK_POLICY_DIAGNOSTIC_V1

Date: 2026-05-20  
Auditor: Claude Code  
Commit: 0af6366  
Builder: Codex

## Verdict: PASS

## Layer Separation: PASS
- Only `research_lab/`, `docs/`, `tests/` changed
- No `core/`, `execution/`, `orchestrator.py`, `main.py`, `settings.py`, or production storage imports
- No runtime contamination

## Methodology Integrity: PASS
- Frozen trial-00095 entry population preserved across all SOL risk scenarios
- Entry count, R-space ER, R-space PF unchanged (1545 approved, ER 2.056, PF 3.49)
- `clone_with_sol_risk()` only modifies `risk_pct` for SOL trades (line 56), not entry selection
- BTC/ETH risk stays 0.35%, only SOL risk varies
- Test `test_evaluate_scenario_keeps_entry_population_for_risk_cap_change` confirms entry population is fixed

## Promotion Safety: PASS
- Builder verdict `SOL_APPROVED_AT_RISK_0.0015` is clearly scoped as offline research-policy only
- Report explicitly states "This does not approve SOL shadow or runtime"
- No promotion artifacts (shadow config, PAPER settings, runtime integration) generated

## Reproducibility & Lineage: PASS
- Hypothesis file `sol_risk_policy_diagnostic.json` declares all gates upfront
- Gates match: `max_capital_dd: 0.06`, `min_portfolio_er: 1.8`, `min_portfolio_pf: 3.0`, `min_sol_approved_trades: 500`, `min_incremental_pnl_pct: 0.01`, `max_capital_dd_increase_vs_btc_eth: 0.02`
- SOL risk caps tested: `[0.0015, 0.0020, 0.0025, 0.0030, 0.0035]`
- Policy selection rule predeclared (lowest capital DD among passing)
- Same datasets as forensic milestone (audited trial-00095 snapshots)

## Data Isolation: PASS
- No source DB writes
- Reads from audited snapshots: `replay-optuna-default-v3-trial-00095.db`, `ethusdt_2022_2026_dataset_v1.db`, `replay-run-sol-historical-2022-2026.db`
- No production storage interaction

## Search Space Governance: PASS
- No parameter tuning beyond predeclared SOL risk cap sensitivity
- Trial-00095 params (sweep thresholds, exits, entry logic) remain frozen
- BTC/ETH risk frozen at 0.35%

## Artifact Consistency: PASS
- Report frontier shows consistent entry population across all scenarios (1545 approved, 905 SOL)
- R-space metrics unchanged (ER 2.056, PF 3.49)
- Capital DD increases with SOL risk as expected (5.24% → 5.32% → 5.40% → 6.08% → 6.81%)
- Incremental PnL increases linearly with SOL risk (251.78% → 347.69% → 443.60% → 539.51% → 635.42%)
- Gate evaluation shows clear pass/fail boundary at 0.30% (capital DD 6.08% > 6.00%)

## Boundary Coupling: PASS
- Portfolio replay harness used correctly (offline artifact trades)
- No backtest/ or settings.py promotion leakage
- Research lab operates independently from live execution path

## Contract Compliance: PASS
- All trades are `ArtifactTrade` with correct `risk_pct` field population
- `capital_metrics()` uses per-trade risk from `risk_by_key` dict
- No type violations

## Determinism: PASS
- Risk cloning is deterministic (symbol-based switch)
- Capital metrics calculation is deterministic (sorted by `opened_at, symbol, trade_id`)
- Policy selection is deterministic (sorted by `capital_dd, -incremental_pnl, sol_risk_pct`)

## State Integrity: N/A
- No state mutation, offline diagnostic only

## Error Handling: PASS
- No uncaught exceptions
- Graceful handling of zero-loss-streak edge case (max-loss fallback)

## Smoke Coverage: PASS
- 6/6 tests pass, including critical boundary tests
- `test_clone_with_sol_risk_keeps_btc_eth_unchanged` - verifies BTC/ETH risk preservation
- `test_evaluate_scenario_keeps_entry_population_for_risk_cap_change` - verifies fixed entry population
- `test_choose_policy_prefers_lowest_capital_drawdown_among_passing` - verifies selection logic
- Tests cover: risk cloning, capital metrics, gate evaluation, policy selection, hypothesis spec validation

## Tech Debt: LOW
- No `NotImplementedError` stubs
- No TODOs
- Minimal duplication (`max_drawdown`, `max_consecutive_losses` shared with forensic diagnostic - acceptable)

## AGENTS.md Compliance: PASS
- Commit discipline clean: `00d7200 research: add SOL risk policy diagnostic`, `8928816 research: fix SOL risk policy gate serialization`, `0af6366 docs: record SOL risk policy diagnostic`
- MILESTONE_TRACKER and DECISIONS_LOG updated correctly
- BTC PAPER bot (PID 815407) remained active during research replay

## Critical Issues
None.

## Warnings
None.

## Observations

1. **Risk frontier validates portfolio safety at reduced SOL size**  
   - 3/5 scenarios pass all gates (0.15%, 0.20%, 0.25%)
   - 2/5 fail at capital DD boundary (0.30% → 6.08% > 6.00%, 0.35% → 6.81% > 6.00%)
   - Selection rule correctly prioritizes lowest DD among passing set (0.15% → 5.24% DD)

2. **Incremental PnL scales linearly with SOL risk**  
   - Delta per 0.05% risk increase ≈ 0.96 percentage points (905 trades × ER 2.12 × 0.0005)
   - 0.15% SOL adds 251.78 pp to baseline 476.24% (total 728.02%)
   - 0.25% SOL would add 443.60 pp (total 919.84%), but at higher DD cost (5.40% vs 5.24%)

3. **Capital DD increase is non-linear near the gate boundary**  
   - 0.15% → 0.25%: DD increases 0.16 pp (5.24% → 5.40%, linear region)
   - 0.25% → 0.30%: DD jumps 0.68 pp (5.40% → 6.08%, crosses into regime-concentrated drawdown)
   - Suggests 2022 crash drawdown becomes dominant driver above 0.25% risk cap

4. **Builder verdict scoping is correct**  
   - `SOL_APPROVED_AT_RISK_0.0015` is clearly research-policy approval, not shadow/runtime approval
   - Report interpretation states "does not approve SOL shadow or runtime"
   - DECISIONS_LOG records this as offline-only milestone

5. **Methodology isolates risk-sizing effect cleanly**  
   - Entry population fixed at 1545 approved (905 SOL)
   - R-space metrics fixed (ER 2.056, PF 3.49)
   - Only capital DD and incremental PnL vary with SOL risk_pct
   - Tests confirm entry count invariance across risk scenarios

## Recommended Next Step

**If user approves:** Design-only milestone for SOL shadow/risk-policy contract.

**Scope:** Document how SOL signals would be shadow-observed without orders, using the approved 0.15% risk cap as the candidate policy. No shadow deployment, no PAPER, no runtime integration. Deliverables: contract specification, shadow metrics collection plan, promotion safety gates for eventual PAPER consideration (blocked separately by user approval + audit).

**Rationale:** Forensic diagnostic identified the DD problem (2022 crash, long loss streaks). Risk-policy diagnostic identified a solution (smaller SOL position size). Before any shadow deployment, the contract must define: setup isolation (SOL sweep/reclaim is separate from BTC/ETH setup), per-setup risk caps, per-setup metrics, portfolio-level arbiter, and promotion gates that block SOL from affecting live capital until PAPER validation proves DD control in forward data.

**Builder recommendation:** Codex (continuity on SOL research branch, portfolio contract design experience from BTC+ETH baseline).

**Target files:** `docs/BLUEPRINT_SOL_SHADOW_CONTRACT.md`, `docs/analysis/*.md` (no code yet - design-only milestone).

**No-touch areas:** `core/`, `execution/`, `orchestrator.py`, `main.py`, `settings.py`, production storage, BTC PAPER bot config.

---

**Audit complete.** Methodology is sound, risk frontier is reproducible, and builder verdict is appropriately scoped. Offline research supports SOL at 0.15% risk cap. Shadow design is the next safe step, but remains blocked from deployment without separate contract audit and user approval.
