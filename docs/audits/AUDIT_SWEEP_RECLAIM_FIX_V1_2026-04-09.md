# AUDIT: SWEEP-RECLAIM-FIX-V1
Date: 2026-04-09
Auditor: Claude Code
Commit: ba1d6d1

## Verdict: MVP_DONE

## Layer Separation: PASS
No cross-layer imports introduced. FeatureEngineConfig remains internal to core/. StrategyConfig owns the public surface. Wiring flows correctly: StrategyConfig → FeatureEngineConfig → detect_equal_levels().

## Contract Compliance: PASS
Features dataclass fields unchanged. MarketSnapshot unchanged. All downstream consumers unaffected.

## Determinism: PASS
detect_equal_levels() is pure — same input produces same output. No new internal state introduced. Bar indices derived from enumerate(recent_15m) which is deterministic per snapshot.

## State Integrity: PASS
No new stateful components. FeatureEngineConfig is a frozen dataclass (slots=True).

## Error Handling: PASS
Empty levels list returns [] (existing guard preserved). span check is index arithmetic — no exception paths.

## Smoke Coverage: WARN
60/60 unit tests green. New deterministic tests cover:
- span filter rejects cluster with span < level_min_age_bars (test_level_min_age_bars_filters_short_span_cluster)
- span filter passes cluster with span == level_min_age_bars (boundary condition correct: `< min_age_bars`, not `<=`)
- param_registry exposes both new params as ACTIVE with correct ranges

Pending acceptance criterion: sweep_detected < 50% on full historical replay (requires live DB backtest run — confirmed pre-RUN4, not blocking MVP_DONE).

## Tech Debt: LOW
No NotImplementedErrors, no TODOs introduced. _to_finite_float fix explicitly deferred to separate micro-commit (tracked).

## AGENTS.md Compliance: PASS
Commit message: WHAT / WHY / STATUS format. 9 files changed in single atomic commit.

## Methodology Integrity: PASS
A: level_min_age_bars enforces temporal persistence requirement for levels — aligns with blueprint "liquidity sweep = rare institutional event".
B: min_hits=3 raises signal-to-noise threshold for level formation.
C2a: weight_sweep_detected and weight_reclaim_confirmed removed as always-true intercepts from _confluence_score(). confluence_min=0.75 correctly reflects reachable variable score (max 2.05). Gate-before-score architecture preserved and now architecturally consistent.

## Promotion Safety: N/A
Not a research lab milestone.

## Reproducibility & Lineage: PASS
Both new params appear in param_registry as ACTIVE — any future Optuna trial that samples them produces a fully reproducible config vector.

## Data Isolation: PASS
No changes to data layer.

## Search Space Governance: PASS
weight_sweep_detected and weight_reclaim_confirmed frozen with explicit documented reason. level_min_age_bars and min_hits added as ACTIVE with curated ranges [2,20] and [2,5]. confluence_min range updated to [0.0, 2.0] to match new max reachable score.

## Artifact Consistency: N/A

## Boundary Coupling: PASS
detect_equal_levels() signature change (list[float] → list[tuple[int, float]]) is contained within feature_engine.py. Function is not exported or imported anywhere else.

---

## Critical Issues
None.

## Warnings
1. sweep_detected < 50% replay smoke pending — run before RUN4 campaign starts to confirm semantic fix has expected effect on signal frequency.
2. _to_finite_float(inf → 0.0) bug in research_lab/objective.py:27 remains — tracked, fix as separate micro-commit before RUN4.

## Observations
1. _RANGE_OVERRIDES still contains entries for weight_sweep_detected and weight_reclaim_confirmed (lines 65-66). These are harmless — FROZEN params are excluded from get_active_params() so Optuna never samples them. Range entries are dead code but not incorrect.
2. B6 HTF levels (deferred, open decision D3) will re-enter detect_equal_levels(). The refactor correctly avoids hardcoding 15m assumptions — indices are bar-relative, not time-relative. B6 path remains clean.

## Recommended Next Step
1. Micro-commit: fix _to_finite_float in research_lab/objective.py (one line, ba1d6d1 base)
2. Await RUN3_DONE from server
3. Run sweep saturation smoke against local btc_bot.db to confirm sweep_detected < 50%
4. Start RUN4 with new clean baseline
