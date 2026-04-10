# AUDIT: SIGNAL-ANALYSIS-V1
Date: 2026-04-10
Auditor: Claude Code
Commit: cef73f6
Builder: Cascade

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
## Promotion Safety: N/A (diagnostic milestone — no candidate promotion)
## Reproducibility & Lineage: PASS
## Data Isolation: PASS
## Search Space Governance: PASS
## Artifact Consistency: PASS
## Boundary Coupling: PASS

---

## What was delivered

**D1 — Volume Lever Audit (COMPLETE)**
- `research_lab/types.py`: `volume_lever: bool` + `volume_direction: str | None` added to
  `ParamSpec` with backward-compatible defaults (False, None)
- `research_lab/param_registry.py`: `_VOLUME_LEVER_MAP` encodes 26 ACTIVE + 3 FROZEN levers;
  wired into all `ParamSpec` constructions via `_build_section_specs`
- `docs/diagnostics/VOLUME_LEVER_AUDIT.md`: full parameter table, permanent governance artifact

Volume lever count: 26 of ~45 ACTIVE parameters. 12 levers identified beyond the handoff's
confirmed minimum of 14. All extensions are correct:
- `sweep_buf_atr`, `reclaim_buf_atr`: directly affect sweep/reclaim detection threshold
- `min_rr`: lower minimum R:R → more signals pass risk gate (correctly a lever)
- `daily_dd_limit`, `weekly_dd_limit`: higher limits → more trades before drawdown stop
- `tfi_impulse_threshold`, `post_liq_tfi_abs_min`, `allow_long_in_uptrend`: all correct

**D2 — Raw Event Study Script (COMPLETE, awaiting production DB execution)**
- `research_lab/diagnostics/event_study_v1.py`: 515 lines, end-to-end runnable
- Authoritative feature config hardcoded, not inferred from code
- Fixed exit model: SL=1.0×ATR, TP=2.0×ATR, max_hold=16 bars — uniform across all events
- Two-pass architecture: Pass 1 collects events + compact bar data; Pass 2 computes forward
  returns and fixed-exit outcomes (correct — avoids look-ahead)
- `_cluster_metadata_for_level`: local helper mirrors detect_equal_levels clustering without
  modifying core/**; correctly extracts (hit_count, age_bars) per swept level
- INSUFFICIENT_SAMPLE guard (n<30) applied per bucket per segment
- P1+MATURE edge count written to JSON output with p<0.10 threshold
- Field name verification: `features.reclaim_detected` and `features.sweep_depth_pct` are
  correct per `core/feature_engine.py` lines 215, 249, 251

**D3 — Regime Decomposition Script (COMPLETE, conditional on D2)**
- `research_lab/diagnostics/regime_decomposition_v1.py`: 342 lines
- Gate check correctly re-applies p<0.05 threshold independently (does NOT rely on D2's
  pre-computed edge_count which uses p<0.10) — iterates p1_mature_summary with own threshold
- `--force` flag available for manual override
- Falls back to default settings if trial-00195 not in store

**D4 — Decision Report (TEMPLATE COMPLETE, numbers pending production execution)**
- `docs/diagnostics/SIGNAL_ANALYSIS_V1.md`: all 4 decision tree branches present
- Objective function vulnerability tracked as explicit open item
- "D4 does NOT make the strategic recommendation" process note preserved
- Instructions for populating [PENDING] values are clear

**Tests: 22 new, 94/94 green (was 72)**
- D1 registry field coverage, D2 helpers (exit model, cluster metadata, t-test, buckets,
  segments, end-to-end minimal DB), D3 gate conditions — all covered

---

## Warnings

**W1: `edge_count` variable in D3 gate check is loaded but unused**
`_check_d2_condition` reads `d2.get("p1_mature_edge_count", 0)` into `edge_count` but
never uses it in the gate decision (gate logic correctly uses its own `qualifying` list).
Dead variable — should be removed or used in the reason string. Non-blocking.

**W2: D4 decision tree branch 1 is incomplete without D1 freeze list**
Decision tree branch 1 ("Signal exists, search problem → reduce to ~20 params, 500+ trials")
does not specify which 26 volume levers to freeze before dimensionality reduction. Without
that specification, a builder tasked with Run #5 design will reduce dimensions without
knowing which levers must be excluded.
Recommended: when populating D4 after execution, Claude Code should annotate branch 1 with
the specific freeze list from VOLUME_LEVER_AUDIT.md.

---

## Observations (non-blocking)

- `min_sweep_depth_pct=0.0` is noted in the JSON meta as `feature_config.min_sweep_depth_pct`
  but is not passed to `FeatureEngineConfig` (likely not a field on that config). The
  documented default of 0.0 is recorded in the output artifact for lineage purposes.
  Acceptable for a diagnostic.

- D3 gate uses p<0.05 for its own condition, while D2's pre-computed `p1_mature_edge_count`
  uses p<0.10. These are intentionally different: D3 triggers on strong evidence,
  D4's decision tree counts edge on moderate evidence. Design is correct but worth noting
  for future readers of the gate logic.

- `weight_sweep_detected`, `weight_reclaim_confirmed`, `weight_force_order_spike` correctly
  appear as volume levers in `_VOLUME_LEVER_MAP` with FROZEN status. This is the historical
  record: they are levers that were frozen specifically to prevent exploitation.
  Run #3 pattern (weight_sweep_detected=4.95) is now structurally documented in the registry.

- The diagnostic milestone is split into infrastructure (this commit) and results (production
  DB execution). This is the correct split. D4 template is unambiguous about what must be
  done before Claude Code can make a strategic recommendation.

---

## Required action before Run #5 design begins

1. Run `python -m research_lab.diagnostics.event_study_v1` against production DB
2. If D2 P1+MATURE edge count >= 3 (p<0.05 strict): run `python -m research_lab.diagnostics.regime_decomposition_v1`
3. Populate `[PENDING]` values in `docs/diagnostics/SIGNAL_ANALYSIS_V1.md`
4. Push populated D4 for Claude Code strategic recommendation
5. Claude Code reads D4 numbers, triggers decision tree branch, and generates Run #5 design
   (or stop recommendation) as the next handoff

Until D4 is populated, Run #5 scope is undefined.

---

## Recommended Next Step

**Execute D2 and D3 against production DB. Populate D4. Push for Claude Code audit.**

No new infrastructure needed. The diagnostic scripts are ready. One command to unblock
the decision tree.
