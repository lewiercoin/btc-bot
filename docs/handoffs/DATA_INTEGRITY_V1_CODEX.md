# CLAUDE HANDOFF -> CODEX

## Checkpoint

- Last commit: `1128284` (`feat: EXPERIMENT-V1-THROUGHPUT deployed, Day 0 data collection started`)
- Current production branch: `experiment-v1-unblock-filters`
- Working tree assumption: clean; Experiment v1 is running and must remain untouched
- Next implementation branch: `data-integrity-v1` (create from current `main`)

## Critical timing and merge discipline

**Start date:** after Experiment v1 checkpoint/end (target date previously discussed: 2026-05-05)

Before that date:
- You MAY create branch `data-integrity-v1`
- You MAY start Task 1 design work (`FeatureQuality` model)
- You MUST NOT merge anything to `main` before Experiment v1 checkpoint/end
- You MUST NOT touch files in `experiment-v1-unblock-filters`

Why: Experiment v1 is collecting baseline data. Any change to `main` risks contaminating interpretation of the experiment.

---

## Before you code

Read these files first:

### Source of truth
- `docs/milestones/DATA_INTEGRITY_V1.md` if present
- GitHub issue #1: `DATA-INTEGRITY-V1: final implementation contract (persistence + bootstrap + quality states)`

### Architecture and project contracts
- `docs/BLUEPRINT_V1.md`
- `docs/BLUEPRINT_RESEARCH_LAB.md` (do not touch `research_lab` in this milestone)
- `AGENTS.md`
- `docs/MILESTONE_TRACKER.md`

### Existing code contracts
- `core/models.py`
- `storage/schema.sql`
- `settings.py`

---

## Milestone: DATA-INTEGRITY-V1

### Goal
Make decision-path data **restart-safe, coverage-aware, and quality-explicit**.

### Scope
Data reliability infrastructure only.

### Out of scope
- session modeling
- execution realism
- parameter tuning
- new external data sources
- threshold/scoring changes
- changes to active Experiment v1 logic/profile

### Architecture principle
**Persistence + bootstrap > restart-from-zero warmup**

Where features depend on history exceeding process lifetime, persist reconstructible state and bootstrap from DB. Do not rely on runtime uptime as the primary maturity signal.

---

## Correct priority order

1. **Task 1:** Structured Feature Quality Model
2. **Task 2:** OI Sample Persistence + Bootstrap
3. **Task 3:** Flow Window Completeness Validation
4. **Task 4:** CVD/Price History Persistence + Bootstrap
5. **Task 5:** Funding Window Integrity
6. **Task 6:** Operational Visibility (Logs + Diagnostics / optional dashboard endpoint)
7. **Task 7:** Integration + Regression Tests

---

## Task details

### Task 1: Structured Feature Quality Model
- Add `FeatureQuality` dataclass to `core/models.py`
- Integrate quality tracking into the **existing** canonical feature model in repo
- Quality states: `ready | degraded | unavailable`
- Include: `reason`, `metadata`, `provenance`

**Critical instruction:**
Before coding, inspect `core/models.py` and extend existing models (`Features`, `MarketSnapshot`, etc.) instead of inventing a parallel abstraction.

### Task 2: OI Sample Persistence + Bootstrap
- Add persistent OI sample storage (append-only)
- Add repository methods to save/load OI samples
- Bootstrap OI history from DB on startup
- Use config-driven horizon (e.g. `settings.oi_baseline_days`)
- Mature OI baseline must survive restart without artificial warmup penalty

### Task 3: Flow Window Completeness Validation
- Replace naive blind trust in `aggTrades(limit=1000)` fallback
- Implement coverage-aware fallback / reconstruction
- Compute explicit `coverage_ratio`
- Use config-driven thresholds for ready/degraded/unavailable

### Task 4: CVD/Price History Persistence + Bootstrap
- Persist minimal bar history required for divergence readiness
- Add repository methods to save/load CVD/price bar history
- Bootstrap CVD history from DB on startup
- Use config-driven bar requirement (e.g. `settings.cvd_divergence_bars`)

### Task 5: Funding Window Integrity
- Validate configured funding lookback against actual loaded history
- Expose truthful completeness status for funding-based features
- No silent clipped horizon

### Task 6: Operational Visibility
- Startup bootstrap summary
- Per-cycle concise feature quality summary in logs
- Structured diagnostics / audit log integration
- Optional low-scope endpoint: `/api/feature-quality`

### Task 7: Integration + Regression Tests
- Restart continuity test
- Cold start correctness test
- WS degradation / REST fallback completeness test
- Funding completeness test
- Regression expectation: no hidden model/scoring changes when data is mature and complete

---

## Target files

### Expected new files
- `storage/migrations/add_oi_samples_table.sql` (or equivalent migration file)
- `storage/migrations/add_cvd_history_table.sql`
- `tests/test_oi_persistence.py`
- `tests/test_cvd_persistence.py`
- `tests/test_flow_completeness.py`
- `tests/test_funding_integrity.py`
- `tests/test_feature_quality_visibility.py`
- `tests/test_data_integrity_integration.py`

### Expected modified files
- `core/models.py`
- `core/feature_engine.py`
- `storage/schema.sql`
- `storage/repositories.py`
- `data/rest_client.py`
- `data/market_data.py`
- `orchestrator.py`
- `settings.py`
- `dashboard/server.py`
- `dashboard/db_reader.py`
- `storage/audit_logger.py`
- `monitoring/metrics.py`
- `scripts/smoke_feature_engine.py`
- `scripts/smoke_recovery.py`

### Must NOT be modified in this milestone
- `research_lab/**`
- backtest logic files (unless a test harness absolutely needs adaptation for compatibility, and only with explicit justification)
- `core/signal_engine.py` for scoring/threshold changes
- `execution/**`
- active Experiment v1 branch/profile

---

## Constraints and boundaries

### In scope
- data persistence
- bootstrap logic
- coverage validation
- quality contracts
- diagnostics visibility

### Out of scope
- session-aware logic
- execution realism
- parameter tuning / Optuna
- new sources like long/short ratio or liquidation clustering
- regime redesign
- threshold changes such as `min_rr`, `confluence_min`, etc.

---

## Your first response must contain

1. Confirmed milestone scope in your own words
2. Restatement of the 7 tasks in your own words
3. Acceptance criteria summary
4. In-scope vs out-of-scope confirmation
5. Ordered implementation plan with files/dependencies/tests
6. Model integration strategy:
   - confirm you inspected `core/models.py`
   - identify the canonical feature/domain model
   - confirm you will extend existing models and avoid parallel abstractions
   - confirm no breaking changes to backtest/research compatibility

---

## Commit discipline

Every commit message must include:
- **WHAT**
- **WHY**
- **STATUS**

Example:

```text
feat(data-integrity): add FeatureQuality model to core/models.py

WHAT: Added FeatureQuality dataclass with status/reason/metadata/provenance fields
WHY: Task 1 foundation - all history-dependent features need explicit quality state
STATUS: Done - integrated with existing Features model, tests pass

Related: DATA-INTEGRITY-V1 Task 1
```

Do not:
- self-mark the milestone as done
- mix multiple tasks in one commit
- skip tests
- merge to `main` before Experiment v1 checkpoint/end

---

## Handoff summary

- Builder: Codex
- Auditor: Claude Code
- Milestone: `DATA-INTEGRITY-V1`
- Implementation branch: `data-integrity-v1`
- Merge gate: audit approval after Task 7
- Post-milestone validation: run Experiment v2 with same config on cleaned data contracts

## Primary references
- Issue #1 in repo (`DATA-INTEGRITY-V1: final implementation contract...`)
- `AGENTS.md`
- `docs/MILESTONE_TRACKER.md`
- `docs/BLUEPRINT_V1.md`

This document is intended to be a stable handoff companion to issue #1.