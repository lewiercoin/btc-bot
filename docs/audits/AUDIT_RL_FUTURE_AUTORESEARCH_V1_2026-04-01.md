# AUDIT: RL-FUTURE Autoresearch Agent Loop v1
Date: 2026-04-01
Auditor: Claude Code
Commit: d1ab0f1

## Verdict: MVP_DONE

## Layer Separation: PASS
`autoresearch_loop.py` depends only on `research_lab/` internals and `backtest/` via `evaluate_candidate`. No imports from live-path modules (`core/`, `execution/`, `orchestrator`). Snapshot I/O is delegated to `db_snapshot.py` per existing pattern.

## Contract Compliance: PASS
`AutoresearchCandidateResult` and `AutoresearchLoopReport` types match `types.py`. `run_autoresearch_loop()` signature matches CLI wiring in `cli.py`. `loop_report.json` is always written; `approval_bundle/` only when top candidate has no blocking risks.

## Determinism: PASS
`_generate_candidate_vectors` is seeded via `random.Random(seed)` — deterministic given fixed seed, history, and param registry. `_rank_key` is a 7-tuple with `candidate_id` as tiebreak — fully deterministic. `test_autoresearch_loop_ranking_is_deterministic` confirms identical ranked output across two runs with the same seed and empty history.

## State Integrity: PASS
Research lab is offline-only. No live-path state mutation. Each candidate gets its own snapshot via `create_trial_snapshot` + `open_snapshot_connection` in try/finally. Source DB not mutated.

## Error Handling: PASS
`store_not_writable` stop path exits the evaluation loop cleanly and always writes the loop report. `baseline_gate_failed` is caught explicitly. No bare `except`. `verify_required_tables` runs before evaluation per candidate.

## Smoke Coverage: PASS (MVP_DONE criteria)
Five autoresearch-specific tests covering:
- Happy path: single-pass, ranked loop report, approval bundle written
- All-blocked path: loop report written, no bundle directory
- Baseline gate failure: `stop_reason=baseline_gate_failed`, empty results, report written
- Nested mode rejection: `ValueError` raised before any evaluation
- Determinism: identical ranked output across two independent runs

Missing (DONE criteria, not MVP_DONE):
- `store_not_writable` mid-loop stop — no smoke test
- LLM advisory path with mock `llm_advisory_fn` — no smoke test

## Tech Debt: LOW
No stubs. No TODOs. No `NotImplementedError`. `_repair_direct_constraints` is a heuristic for `tp1_atr_mult < tp2_atr_mult`; it works but is not generalized through `constraints.py`. Acceptable for v1.

## AGENTS.md Compliance: PASS
Commits follow WHAT/WHY/STATUS discipline. No self-marking as DONE. Working tree clean at checkpoint.

## Methodology Integrity: PASS
`walkforward_mode != "post_hoc"` raises `ValueError` before any evaluation — nested is hard-gated, not soft-warned. Evaluation uses `evaluate_candidate` + `run_walkforward` directly, not `run_optuna_study` or `run_optimize_loop`. The agent evaluates pre-generated vectors — matches blueprint contract exactly.

## Promotion Safety: PASS
`write_approval_bundle` writes artifacts only. `settings.py` is not touched. Approval bundle is gated on `top_result.blocking_risks` being empty. All-blocked path verified by smoke test — no bundle directory created.

## Reproducibility & Lineage: PASS (MVP_DONE level)
`protocol_hash` is injected into each evaluation via `dataclasses.replace` before persistence. `seed`, `date_range_start`, `date_range_end`, `run_id` (UUID), and `protocol_hash` are all fields in `AutoresearchLoopReport` and written to `loop_report.json`. Commit SHA not persisted in experiment store — tracked as pre-existing lineage debt, not introduced here.

## Data Isolation: PASS
Per-candidate snapshot isolation via `create_trial_snapshot`. Source DB connection is never passed into evaluation directly — only snapshot connection is used. `verify_required_tables` runs on snapshot before evaluation.

## Search Space Governance: PASS
`_generate_candidate_vectors` calls `get_active_params()` — only ACTIVE parameters are sampled. FROZEN, DEFERRED, and UNSUPPORTED parameters are not reachable through this path. `_normalize_active_vector` fills missing active params from base defaults, not from frozen params.

## Artifact Consistency: PASS
Trial + walk-forward report + recommendation all persisted to experiment store before loop report is written. `protocol_hash` is consistently propagated through evaluation → save_trial → loop_report. Approval bundle is built from the persisted recommendation (via `recommendations_by_candidate_id`) not from a parallel construction.

## Boundary Coupling: PASS
`autoresearch_loop.py` does not import from `walkforward.py`'s nested path (`run_nested_walkforward`). It uses `run_walkforward` only. The autoresearch module has no knowledge of Optuna. All optimization infrastructure is bypassed by design.

---

## Critical Issues (must fix before next milestone)
None.

## Warnings (fix soon)
1. **`store_not_writable` stop path lacks smoke test.** The mid-loop store failure branch (lines 563-565, 576-579) is exercised by exception injection but no test currently simulates this. This is a DONE criterion gap, not MVP_DONE.
2. **LLM advisory path has no smoke test.** `llm_advisory_fn` contract (reorder-only, rationale-count check) is implemented and enforced but not smoke-tested. This is a DONE criterion gap.

## Observations (non-blocking)
- `_repair_direct_constraints` duplicates the `tp1 < tp2` constraint that `validate_param_vector` also enforces. The repair runs during generation; the filter runs after. This is belt-and-suspenders; the filter would drop vectors that repair failed to fix. Not a bug.
- `stop_reason="completed"` is upgraded to `"max_candidates_reached"` post-loop based on `len(filtered_vectors) >= max_candidates`. This is correct but subtle — the stop reason reflects whether the cap was hit, not whether evaluation completed. If fewer vectors pass the constraint filter than `max_candidates`, reason stays `"completed"`.
- `_history_trial_sort_key` uses `recommendation_priority` from the last N recommendations to bias hypothesis generation toward previously recommended regions. This is the gradient-free exploitation heuristic described in the blueprint. Advisory only — does not affect evaluation.

## Recommended Next Step
Close RL-FUTURE as MVP_DONE in MILESTONE_TRACKER.md and BLUEPRINT_RESEARCH_LAB.md roadmap. 

No immediate follow-on milestone is required. The two DONE-level gaps (store_not_writable smoke test, LLM advisory smoke test) are tracked here and should be folded into the next milestone that touches autoresearch, or addressed as a standalone RL-AUTORESEARCH-HARDENING milestone when the operator is ready to pursue DONE status.
