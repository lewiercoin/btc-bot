# AUDIT: Experiment Management
Date: 2026-04-24
Auditor: Claude Code
Commit: 9f00457

## Verdict: DONE

## Experiment Isolation: PASS
## Reproducibility: PASS
## Production Contamination Risk: PASS
## Experiment ID / Lineage: PASS
## Seed Fixation: PASS
## DB Isolation: PASS

## Findings

### Evidence reviewed
- `research_lab/` — complete experiment management system
- `research_lab/experiment_store.py` — trial persistence and lineage tracking
- `research_lab/db_snapshot.py` — per-trial DB snapshot creation
- `research_lab/protocol.py` — protocol versioning and deterministic hashing
- `research_lab/param_registry.py` — parameter sandbox (ACTIVE, FROZEN, DEFERRED, UNSUPPORTED)
- `docs/BLUEPRINT_RESEARCH_LAB.md` — explicit system boundary and disallowed behaviors
- `docs/RESEARCH_LAB_WORKFLOW.md` — two-phase workflow documentation
- `.env.example` — no research-specific environment variables exposed
- `settings.py` — `load_settings(profile="research")` vs `load_settings(profile="live")`

### Assessment summary
- **Experiment isolation is production-grade.** Each Optuna trial runs against its own SQLite snapshot (created by `db_snapshot.py`). Trials cannot contaminate each other or production DB.
- **Reproducibility is comprehensive.** Trial lineage includes: `protocol_hash`, `search_space_signature`, `trial_context_signature`, `baseline_version`, `seed`, date range, commit context. This enables exact experiment reproduction.
- **Production contamination risk is zero by design.** `BLUEPRINT_RESEARCH_LAB.md` explicitly forbids: mutating live path modules, writing to `settings.py`, bypassing approval artifacts. Research lab is offline-only.
- **Experiment IDs are deterministic and traceable.** `protocol_hash` computed from protocol JSON (date range, walk-forward config, search space). `trial_id` from Optuna. All stored in `research_lab/research_lab.db`.
- **Seed fixation exists for reproducibility.** Protocol JSON includes `seed` field. Optuna sampler accepts seed for deterministic trial generation.
- **DB isolation is explicit.** Source DB (`storage/btc_bot.db`) is read-only input. Each trial gets fresh snapshot in `research_lab/snapshots/`. No shared mutable state.

## Critical Issues (must fix before next milestone)
None identified. Experiment isolation and reproducibility are production-grade.

## Warnings (fix soon)
None identified.

## Observations (non-blocking)
- **Two-phase workflow is well-documented.** Phase 1 (Optuna discovery) → Phase 2 (autoresearch refinement). Warm-start filtering by `protocol_hash` and `search_space_signature` prevents cross-protocol contamination.
- **Approval bundle generation is gated.** `research_lab/approval.py` checks blocking promotion risks before writing artifacts. No auto-promotion path exists.
- **Experiment store is SQLite-based.** `research_lab/research_lab.db` persists trials, walk-forward reports, recommendations. This enables post-campaign analysis and replay.
- **Parameter sandbox prevents accidental architectural changes.** `param_registry.py` marks architectural parameters (`ema_fast=50`, `ema_slow=200`) as FROZEN, preventing Optuna from sampling them.
- **Research lab has explicit non-goals.** Blueprint states: "Research Lab explicitly does NOT: auto-promote candidates into `settings.py`, mutate live execution, place orders, hide methodology changes inside bugfix milestones."
- **Settings profile separation exists.** `load_settings(profile="research")` vs `load_settings(profile="live")` prevents research overrides from bleeding into production.

## Recommended Next Step
Experiment management is production-ready. No action required. This is a model implementation for research lab isolation and reproducibility.
